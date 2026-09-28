# Demo model card

## Intended use

These models support a portfolio demonstration of customer segmentation, churn prioritization, purchase propensity, and product ranking. They are decision-support signals, not automated eligibility, pricing, credit, employment, healthcare, or other high-impact decisions.

## Training data

The checked-in evaluation metadata comes from `data/demo/demo_transactions.csv`, a deterministic synthetic retail dataset with 240 customers and activity between December 2009 and December 2011. It is designed to contain learnable lifecycle and purchase-cadence patterns. Results must be labeled **synthetic demo metrics**.

## Label and split contracts

- Churn is no purchase during the 90 days after a cutoff.
- Propensity is any purchase during the 30 days after a cutoff.
- Monthly historical cutoffs build features without future transactions.
- Cutoffs are divided chronologically into 60% training, 20% validation, and 20% test periods.
- The validation set chooses the F1 decision threshold; the test set is untouched until final evaluation.

## Verified synthetic demo results

| Model | Metric | Validation | Test |
| --- | --- | ---: | ---: |
| Churn | F1 | 0.853 | 0.927 |
| Churn | ROC-AUC | 0.959 | 0.989 |
| Churn | PR-AUC | 0.875 | 0.978 |
| Propensity | F1 | 0.869 | 0.909 |
| Propensity | ROC-AUC | 0.916 | 0.953 |
| Propensity | PR-AUC | 0.935 | 0.960 |

Segmentation selected K=3 with silhouette 0.353 and repeated-seed stability 0.991. The recommender's leave-last-order-out evaluation produced Hit Rate@10 of 0.075 and MRR@10 of 0.021 across 240 eligible synthetic customers.

## Limitations

Synthetic lifecycle patterns are cleaner than real customer behavior, so these scores are not expected in production. Online Retail II has no marketing exposure, support activity, customer acquisition channel, demographic attributes, or verified churn event. “Churn” is therefore an inactivity proxy. Recommendations optimize historical co-occurrence rather than incremental revenue, margin, stock, or long-term customer value.

## Before production

Retrain on organization-specific data; validate calibration and subgroup performance; add drift and freshness monitoring; compare against simple baselines; run controlled campaign experiments; constrain recommendations using inventory, consent, and business policy; and require human review of customer-facing actions.
