# Change decision: raw_orders.total_amount

## Proposed change

- Type: drop_column
- Rationale: Retire a legacy field before the next data contract release.

## DataHub evidence

- Downstream assets: 6
- High-criticality assets: 5
- Direct owners: Analytics Engineering, ML Platform, Retention Science, Revenue Operations
- Unowned assets: 1
- Risk score: 100/100
- Decision: block deployment

## Required rollout

1. Merge the generated compatibility patch.
2. Validate every asset in the attached DataHub lineage graph.
3. Assign an owner to the affected Airflow job.
4. Obtain owner approval.
5. Write completion evidence back to DataHub.

