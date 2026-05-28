from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5"
)

# s1 = "如何学习Python"
# s2 = "Python入门教程"
# s3 = "红烧牛肉做法"

s1 = "这个怎么做"
s2 = "如何实现"
s3 = "红烧牛肉做法"

e1 = model.encode(s1)
e2 = model.encode(s2)
e3 = model.encode(s3)

# 余弦相似度 两个语义坐标夹角是否接近
print(cos_sim(e1, e2))
print(cos_sim(e1, e3))