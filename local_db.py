from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from qdrant_client.models import PointStruct

client = QdrantClient("localhost", port=6333)


# client.create_collection(
#     collection_name="test_collection",
#     vectors_config=VectorParams(size=4, distance=Distance.DOT),
# )


operation_info = client.upsert(
    collection_name="test_collection",
    wait=True,
    points=[
        PointStruct(id=1, vector=[0.05, 0.61, 0.76, 0.74], payload={"city": "Berlin"}),
        PointStruct(id=2, vector=[0.19, 0.81, 0.75, 0.11], payload={"city": "London"}),
        PointStruct(id=3, vector=[0.36, 0.55, 0.47, 0.94], payload={"city": "Moscow"}),
        PointStruct(id=4, vector=[0.18, 0.01, 0.85, 0.80], payload={"city": "New York"}),
        PointStruct(id=5, vector=[0.24, 0.18, 0.22, 0.44], payload={"city": "Beijing"}),
        PointStruct(id=6, vector=[0.15, 0.05, 0.5, 0.41], payload={"city": "go to London"}),
        PointStruct(id=7, vector=[0.35, 0.03, 0.14, 0.42], payload={"city": "City of Westminster"}),
        PointStruct(id=8, vector=[0.25, 0.09, 0.6, 0.26], payload={"city": "Buckingham Palace"}),
    ],
)

print("添加有效载荷",operation_info)


search_result = client.query_points(
    collection_name="test_collection",
    query=[0.2, 0.1, 0.9, 0.7],
    with_payload=False,
    limit=3
).points

print("查询最相似的向量", search_result)


from qdrant_client.models import Filter, FieldCondition, MatchValue

search_result = client.query_points(
    collection_name="test_collection",
    query=[0.2, 0.1, 0.9, 0.7],
    query_filter=Filter(
        must=[FieldCondition(key="city", match=MatchValue(value="London"))]
    ),
    with_payload=True,
    limit=3,
).points

print("添加筛选器", search_result)