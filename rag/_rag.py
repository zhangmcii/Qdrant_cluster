import os

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import numpy as np

try:
    from rag.data import text
except ImportError:
    from data import text


COLLECTION_NAME = "my_md"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


class Index:
    """加载文档 拆分文档 存储文档"""

    def __init__(self):
        self.md = None
        self.all_splits = []
        self.payloads = []
        self.vectors = None
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    def load_md(self):
        self.md = text

    def text_split(self):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
        )
        self.all_splits = text_splitter.create_documents([self.md])

    def embedding(self):
        model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        chunk_texts = [doc.page_content for doc in self.all_splits]
        self.vectors = model.encode(
            chunk_texts,
            show_progress_bar=True,
        )
        self.payloads = [
            {
                "content": doc.page_content,
                "start_index": doc.metadata.get("start_index"),
            }
            for doc in self.all_splits
        ]
        print("vectors.shape:", self.vectors.shape)
        np.save("./rag/md.npy", self.vectors, allow_pickle=False)

    def store_to_qdrant(self, recreate=True):
        if self.vectors is None:
            raise ValueError("请先执行 embedding() 生成向量后再写入 Qdrant。")

        collection_exists = self.client.collection_exists(COLLECTION_NAME)
        if recreate and collection_exists:
            self.client.delete_collection(COLLECTION_NAME)
            collection_exists = False

        if not collection_exists:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

        points = [
            PointStruct(id=idx, vector=vector.tolist(), payload=payload)
            for idx, (vector, payload) in enumerate(zip(self.vectors, self.payloads))
        ]
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )

    def index(self, recreate=True):
        self.load_md()
        print("已加载文件")

        self.text_split()
        print("已分割")

        self.embedding()
        print("已嵌入")

        self.store_to_qdrant(recreate=recreate)
        print("已存储")


class Rag:
    """检索 生成"""

    def __init__(self, query_text):
        self.collection_name = COLLECTION_NAME
        self.model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        self.qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.llm_client = None
        if self.api_key:
            self.llm_client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
            )
        self.query_text = query_text
        self.context = ""

    def retrieve(self, query_text=None, limit=3):
        query_text = query_text or self.query_text
        vector = self.model.encode(query_text).tolist()

        search_result = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
        ).points
        # print(f"检索结果:{search_result}")
        if not search_result:
            raise ValueError(
                f"collection `{self.collection_name}` 中没有检索到结果，请先确认是否已经完成索引构建。"
            )
        self.context = "\n\n".join(
            point.payload["content"]
            for point in search_result
            if point.payload and point.payload.get("content")
        )
        if not self.context:
            raise ValueError(
                "检索到了结果，但 payload 里没有可用的 content 字段。"
            )
        return search_result

    def build_prompt(self):
        return f"""
                请基于以下资料回答问题。

                资料：
                {self.context}

                问题：
                {self.query_text}

                要求：
                1. 仅基于资料回答
                2. 不要编造不存在的信息
                3. 简洁清晰
                """.strip()

    def chat(self):
        if not self.context:
            raise ValueError("请先执行 retrieve()，拿到上下文后再调用 chat()。")
        if not self.llm_client:
            raise ValueError("未设置 DEEPSEEK_API_KEY，无法调用生成模型。")

        prompt = self.build_prompt()
        response = self.llm_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        print("\n=== LLM 回答 ===")
        print(response.choices[0].message.content)


if __name__ == "__main__":
    # 生成索引；默认重建 collection，避免重复执行时残留旧数据
    index = Index()
    index.index()

    query = "qps相比之前提升了多少"

    # 检索生成
    rag = Rag(query)
    results = rag.retrieve()
    print(f"命中 {len(results)} 条结果")
    rag.chat()
