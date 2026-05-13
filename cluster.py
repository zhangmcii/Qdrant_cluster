from qdrant_client import QdrantClient, models
from config import documents


class Cluster:
    """ Qdrant"""
    
    def __init__(self):
        self.COLLECTION_NAME="my_books"
        self.EMBEDDING_MODEL="sentence-transformers/all-minilm-l6-v2"
        self.QDRANT_URL = "https://acf89ac8-33b3-4c85-b75e-8b0350c26df3.eu-west-1-0.aws.cloud.qdrant.io:6333"
        self.QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6YmVjY2YyZTktOTkyZC00OGVhLTk0NWMtYTczOWNkNzhhMjMwIn0.Uo3YdSrNCWhokLjOL3QyJ_iA1SMkPZBk1ChzHhrBDKE"
        self.documents = documents
        
        # 连接cluster
        self.client = QdrantClient(
            url=self.QDRANT_URL,
            api_key=self.QDRANT_API_KEY,
            cloud_inference=True
        )

    def create_collections(self):
        """创建collections"""
        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=384,  # Vector size is defined by used model
                distance=models.Distance.COSINE,
            ),
        )
        print(self.client.get_collections())



    def upload_points(self):
        """上传documents"""
        self.client.upload_points(
            collection_name=self.COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=idx,
                    vector=models.Document(
                        text=doc["description"],
                        model=self.EMBEDDING_MODEL
                    ),
                    payload=doc
                )
                for idx, doc in enumerate(self.documents)
            ],
        )

    def query(self, text="外星文明"):
        """查询"""
        hits = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=models.Document(
                text=text,
                model=self.EMBEDDING_MODEL
            ),
            limit=3,
        ).points

        print(f"query_text: {text}")
        for hit in hits:
            print(hit.payload, "score:", hit.score)


    def create_index(self):
        """创建索引"""
        field_name="year"
        self.client.create_payload_index(
            collection_name=self.COLLECTION_NAME,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.INTEGER,
        )
        print(f"{field_name}字段 索引创建完成")

    def query_filter(self, text="外星文明", year=2000):
        """应用筛选器来缩小查询结果范围"""
        hits = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=models.Document(
                text=text,
                model=self.EMBEDDING_MODEL
            ),
            query_filter=models.Filter(
                must=[models.FieldCondition(key="year", range=models.Range(gte=year))]
            ),
            limit=2,
        ).points

        print(f"query_text: {text}")
        for hit in hits:
            print(hit.payload, "score:", hit.score)


if __name__ == '__main__':
    c = Cluster()
    # c.query("社会崩塌")
    # c.create_index()

    
    c.query_filter(text="文明冲突", year=2006)

