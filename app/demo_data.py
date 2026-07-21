from __future__ import annotations

from app.models import Criticality, DataEntity, FieldDefinition, LineageEdge


def field(name: str, type_: str, *, nullable: bool = True, tags: list[str] | None = None):
    return FieldDefinition(name=name, type=type_, nullable=nullable, tags=tags or [])


DEMO_ENTITIES = [
    DataEntity(
        urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,commerce.raw_orders,PROD)",
        name="raw_orders",
        entity_type="dataset",
        platform="Snowflake",
        owner="Commerce Data",
        domain="Commerce",
        criticality=Criticality.HIGH,
        description="Raw ecommerce orders landed from the transactional database.",
        fields=[
            field("order_id", "STRING", nullable=False),
            field("customer_id", "STRING", nullable=False, tags=["PII"]),
            field("status", "STRING"),
            field("total_amount", "DECIMAL(12,2)"),
            field("currency", "STRING"),
            field("created_at", "TIMESTAMP"),
        ],
    ),
    DataEntity(
        urn="urn:li:dataset:(urn:li:dataPlatform:dbt,commerce.stg_orders,PROD)",
        name="stg_orders",
        entity_type="dbt model",
        platform="dbt",
        owner="Analytics Engineering",
        domain="Commerce",
        criticality=Criticality.HIGH,
        fields=[
            field("order_id", "STRING", nullable=False),
            field("customer_id", "STRING", tags=["PII"]),
            field("order_status", "STRING"),
            field("gross_revenue", "DECIMAL(12,2)"),
            field("ordered_at", "TIMESTAMP"),
        ],
    ),
    DataEntity(
        urn="urn:li:dataset:(urn:li:dataPlatform:dbt,commerce.fct_orders,PROD)",
        name="fct_orders",
        entity_type="dbt model",
        platform="dbt",
        owner="Analytics Engineering",
        domain="Commerce",
        criticality=Criticality.MISSION_CRITICAL,
        fields=[
            field("order_id", "STRING", nullable=False),
            field("customer_id", "STRING", tags=["PII"]),
            field("order_status", "STRING"),
            field("gross_revenue", "DECIMAL(12,2)"),
            field("order_date", "DATE"),
        ],
    ),
    DataEntity(
        urn="urn:li:dataset:(urn:li:dataPlatform:looker,commerce.executive_revenue,PROD)",
        name="Executive Revenue Dashboard",
        entity_type="dashboard",
        platform="Looker",
        owner="Revenue Operations",
        domain="Finance",
        criticality=Criticality.MISSION_CRITICAL,
        fields=[
            field("gross_revenue", "NUMBER"),
            field("order_date", "DATE"),
            field("order_status", "STRING"),
        ],
    ),
    DataEntity(
        urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,ml.customer_features,PROD)",
        name="customer_features",
        entity_type="feature table",
        platform="Snowflake",
        owner="ML Platform",
        domain="Machine Learning",
        criticality=Criticality.HIGH,
        fields=[
            field("customer_id", "STRING", nullable=False, tags=["PII"]),
            field("lifetime_value", "FLOAT"),
            field("days_since_last_order", "INTEGER"),
        ],
    ),
    DataEntity(
        urn="urn:li:mlModel:(churn_prediction_v3,PROD)",
        name="churn_prediction_v3",
        entity_type="ML model",
        platform="SageMaker",
        owner="Retention Science",
        domain="Machine Learning",
        criticality=Criticality.HIGH,
        fields=[
            field("customer_id", "STRING"),
            field("churn_probability", "FLOAT"),
        ],
    ),
    DataEntity(
        urn="urn:li:dataJob:(airflow,commerce_daily,refresh_executive_revenue)",
        name="refresh_executive_revenue",
        entity_type="pipeline job",
        platform="Airflow",
        owner=None,
        domain="Commerce",
        criticality=Criticality.MEDIUM,
        fields=[],
    ),
]


DEMO_EDGES = [
    LineageEdge(
        source=DEMO_ENTITIES[0].urn,
        target=DEMO_ENTITIES[1].urn,
        field_mappings={
            "order_id": ["order_id"],
            "customer_id": ["customer_id"],
            "status": ["order_status"],
            "total_amount": ["gross_revenue"],
            "created_at": ["ordered_at"],
        },
    ),
    LineageEdge(
        source=DEMO_ENTITIES[1].urn,
        target=DEMO_ENTITIES[2].urn,
        field_mappings={
            "order_id": ["order_id"],
            "customer_id": ["customer_id"],
            "order_status": ["order_status"],
            "gross_revenue": ["gross_revenue"],
            "ordered_at": ["order_date"],
        },
    ),
    LineageEdge(
        source=DEMO_ENTITIES[2].urn,
        target=DEMO_ENTITIES[3].urn,
        field_mappings={
            "gross_revenue": ["gross_revenue"],
            "order_date": ["order_date"],
            "order_status": ["order_status"],
        },
    ),
    LineageEdge(
        source=DEMO_ENTITIES[2].urn,
        target=DEMO_ENTITIES[4].urn,
        field_mappings={
            "customer_id": ["customer_id"],
            "gross_revenue": ["lifetime_value"],
            "order_date": ["days_since_last_order"],
        },
    ),
    LineageEdge(
        source=DEMO_ENTITIES[4].urn,
        target=DEMO_ENTITIES[5].urn,
        field_mappings={
            "customer_id": ["customer_id"],
            "lifetime_value": ["churn_probability"],
        },
    ),
    LineageEdge(
        source=DEMO_ENTITIES[2].urn,
        target=DEMO_ENTITIES[6].urn,
        relationship="scheduled by",
        field_mappings={"gross_revenue": [], "order_date": []},
    ),
]

