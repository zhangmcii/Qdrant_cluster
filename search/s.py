import numpy as np
import json
import pandas as pd
import os

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance


def encode_data():
    if os.path.exists("./search/startup_vectors.npy"):
        print("已存在startup_vectors.npy 跳过")
        return 
    # 下载并创建一个预训练的句子编码器
    model = SentenceTransformer(
        # "all-MiniLM-L6-v2", device="cuda"
        "all-MiniLM-L6-v2",
        device="cpu",
    )  # or device="cpu" if you don't have a GPU

    # 读取原始数据文件
    df = pd.read_json("./startups_demo.json", lines=True)

    # 对所有创业公司描述进行编码，为每个创业公司创建一个嵌入向量
    vectors = model.encode(
        [row.alt + ". " + row.description for row in df.itertuples()],
        show_progress_bar=True,
    )

    print("vectors.shape:", vectors.shape)

    # 将保存的矢量图下载到一个名为“startup_vectors”的文件中
    np.save("startup_vectors.npy", vectors, allow_pickle=False)


def upload_to_local_Qdrant():
    client = QdrantClient("http://localhost:6333")

    if not client.collection_exists("startups"):
        client.create_collection(
            collection_name="startups",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

    fd = open("./startups_demo.json")

    # payload is now an iterator over startup data
    payload = map(json.loads, fd)

    # Load all vectors into memory, numpy array works as iterable for itself.
    # Other option would be to use Mmap, if you don't want to load all data into RAM
    vectors = np.load("./startup_vectors.npy")

    # 上传数据到 本地Qdrant的 Docker 镜像。
    client.upload_collection(
        collection_name="startups",
        vectors=vectors,
        payload=payload,
        ids=None,  # Vector ids will be assigned automatically
        batch_size=256,  # How many vectors will be uploaded in a single request?
    )


if __name__ == "__main__":
    # 编码数据
    encode_data()

    # 上传数据
    upload_to_local_Qdrant()
