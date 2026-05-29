text = """
# 首页加载太慢？我是如何把 QPS 从“个位数”提升 6 倍的

网站上线后，我兴致勃勃地测了一下首页的 QPS（每秒查询率），结果当场自闭：**不到 9**。
这意味着只要有 10 个人同时狂刷首页，服务器就可能开始“思考人生”了。

这篇复盘文章，将带你从**带宽计算**到**代码排查**，一步步揪出拖垮性能的 4 个“罪魁祸首”，最终将 QPS 提升 6 倍，接口响应速度提升 5 倍以上。

## 01. 案发现场：惨淡的 QPS

**服务器配置：**

* CPU/内存：4核 4GB
* 带宽：3Mbps (这很关键！)
* 架构：Vue + Flask + Nginx
* 启动方式：Gunicorn (Eventlet worker)

**测试工具：wrk**
推荐用 `wrk`，它是 Linux/Mac 下最简单的 HTTP 压测工具，比 AB 测试更直观。

```bash
# 模拟 50 个用户并发，持续压测 10 秒
wrk -t4 -c50 -d10s https://191718.com/api/posts

```

**初始测试结果：**

```text
Running 10s test @ https://191718.com/api/posts
  Requests/sec:      8.74  <-- 惨不忍睹
  Transfer/sec:      2.30KB
  Socket errors:     timeout 75

```

**QPS ≈ 8.74**，且有大量超时。问题出在哪？是服务器太渣，还是代码太烂？

---

## 02. 第一步排查：算算“物理上限”

在怀疑代码之前，先算算硬件瓶颈。很多时候，**贫穷（带宽）限制了你的并发**。

* **带宽换算：** 3 Mbps ≈ 375 KB/s
* **接口现状：** 我的接口返回了大量 JSON 数据（用户信息、文章列表等）。

**假设每个请求返回 30KB 数据（这是未优化前的常见大小）：**

> 理论最高 QPS = 总带宽 / 单请求大小
> 375 KB/s ÷ 30 KB ≈ **12.5 QPS**

**结论：** 哪怕代码写得飞快，3Mbps 的小水管撑死也只能跑 12 QPS。带宽确实在卡脖子，但 8.74 离 12 还有差距，说明代码逻辑也有问题。

---

## 03. 深度优化：揪出 4 个性能杀手

经过代码走查，我发现了 4 个严重拖后腿的问题。

### 杀手 1：经典的 N+1 查询问题

这是新手最容易犯的错误。加载文章列表时，只执行了 1 条 SQL 查出 10 篇文章，但在遍历每篇文章时，又去查了作者、评论数、点赞数。

**糟糕的代码：**

```python
# 1. 先查出 10 篇文章 (1条SQL)
posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()

for post in posts:
    # 2. 循环里也就是 N 次查询
    print(post.author.username)   # 额外查询作者
    print(post.comments.count())   # 额外查询评论数
    print(post.likes.count())    # 额外查询点赞数

```

**后果：** 10 篇文章，执行了 1 + （1 + 1 + 1）* 10 = 31条 SQL。

** 优化方案：预加载 (Eager Loading)**
使用 SQLAlchemy 的 `joinedload` 或 `subqueryload`，在第一条 SQL 就把关联数据抓回来。

```python
# 一次性把 author 表关联查出来
posts = Post.query.options(joinedload(Post.author))\
    .order_by(Post.created_at.desc()).limit(10).all()

```

### 杀手 2：错用的 Eventlet 模式

我之前的启动命令是：
`gunicorn -k eventlet -w 4 app:app`

**误区：** 很多人认为 Eventlet/Gevent 是“高并发神器”。
**真相：** Eventlet 适合 **I/O 密集且全异步** 的场景（如 WebSocket、长轮询）。但我的接口里包含大量 **同步阻塞** 操作（标准 SQLAlchemy 查询、JSON 序列化、JWT 运算）。在这种场景下，异步 Worker 并不比同步 Worker 强，甚至因为上下文切换导致更慢。

** 优化方案：分离服务**

* **主 API (HTTP)：** 改回同步 Worker (`-w 8`)，处理传统的 CRUD 请求更稳。
* **Socket.IO 服务：** 保持使用 Eventlet，专门处理即时通讯。

### 杀手 3：接口里的“隐形炸弹” (外部 API)

我在测试中发现，每次请求耗时极不稳定。排查发现，为了记录访问日志，我在接口装饰器里调用了一个**外部 API 来解析用户 IP 归属地**。

这个 HTTP 请求可能耗时 200ms~1s。**这意味着：用户只是想看个首页，我却让他等我查完 IP 归属地再进门。**

** 优化方案：异步任务**
将耗时操作丢给 Celery 消息队列。

```python
# 优化前：同步等待
def log_visitor(ip):
    location = requests.get(f"http://ip-api.com/{ip}").json() # 阻塞！
    save_to_db(ip, location)

# 优化后：丢进队列，立刻返回
@celery.task
def async_log_visitor(ip):
    location = requests.get(f"http://ip-api.com/{ip}").json()
    save_to_db(ip, location)

```

### 杀手 4：不仅慢，还很“胖”

回到带宽问题。前端首页其实只展示文章摘要（比如前 200 个字），但我后端接口偷懒了，直接返回了 Markdown **全文**。

* **现象：** 首页请求下载内容耗时高达 **524ms**。
* **原因：** 传输了大量无用数据，占满了 3Mbps 的带宽。

** 优化方案：字段截取**
后端 SQL 查询时只取摘要。

---

## 04. 优化后的“起飞”时刻

改完上述 4 点，重新部署，再次执行同样的压测命令：

```bash
wrk -t4 -c50 -d10s https://191718.com/api/posts

```

**最终结果：**

```text
Running 10s test @ https://191718.com/api/posts
  Latency     612.55ms (平均延迟大幅降低)
  Requests/sec:     54.54
  Transfer/sec:    269.80KB

```

### 数据对比

| 指标 | 优化前 | 优化后 | 提升幅度 |
| --- | --- | --- | --- |
| **QPS** | 8.74 | **54.54** | **6.3 倍** |
| **等待响应时间 (TTFB)** | 573ms | **105ms** | 速度提升 5 倍 |
| **内容下载耗时** | 524ms | **0.62ms** | 几乎瞬间完成 |

### 总结

这次优化并没有引入高大上的缓存（Redis 还没发力呢），仅仅是修复了逻辑缺陷：

1. **减负：** 接口不返回多余字段，节省带宽（从 30KB 降到几 KB）。
2. **解耦：** 耗时的 IP 查询丢给 Celery。
3. **合并：** 解决 N+1，减少数据库交互次数。
4. **选对工具：** 根据业务类型选择合适的 Gunicorn Worker。

对于绝大多数中小网站，**带宽**和**低效的 SQL** 往往是最大的瓶颈。在升级服务器配置之前，不妨先看看代码是不是在“甚至”拖后腿。

"""