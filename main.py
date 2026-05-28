import faiss
import numpy as np

# 10000 条数据
data = np.random.random((10000, 128)).astype('float32')

# 创建索引
index = faiss.IndexFlatL2(128)

# 添加数据
index.add(data)

# 查询
query = np.random.random((1, 128)).astype('float32')

# 搜索最相近的5个
D, I = index.search(query, 5)

print(I)
print(D)