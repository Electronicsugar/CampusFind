"""Retrieval and abstention metrics with explicit denominators."""
import math


def summarize(rows, threshold=None):
    positives = [r for r in rows if r['positive_ids']]
    negatives = [r for r in rows if not r['positive_ids']]
    def mean(values):
        return sum(values)/len(values) if values else None
    def recall(row, k):
        return len(set(row['ranking'][:k]) & set(row['positive_ids']))/len(row['positive_ids'])
    def reciprocal(row):
        return next((1/i for i,c in enumerate(row['ranking'],1) if c in row['positive_ids']),0)
    def average_precision(row):
        hits=0;total=0.
        for rank,candidate in enumerate(row['ranking'],1):
            if candidate in row['positive_ids']:
                hits+=1;total+=hits/rank
        return total/len(row['positive_ids'])
    result = {'queries':len(rows),'positive_queries':len(positives),'no_match_queries':len(negatives),
              'recall_at_1':mean([recall(r,1) for r in positives]),
              'recall_at_5':mean([recall(r,5) for r in positives]),
              'mrr':mean([reciprocal(r) for r in positives]),
              'mean_average_precision':mean([average_precision(r) for r in positives]),
              'wrong_top1_on_positive_queries':sum(bool(r['ranking']) and r['ranking'][0] not in r['positive_ids'] for r in positives),
              'no_match_queries_with_proposals':sum(bool(r['ranking']) for r in negatives),
              'proposal_no_match_rejection':mean([int(not r['ranking']) for r in negatives])}
    if threshold is None:
        result['acceptance'] = None  # Suggestions do not constitute identity acceptance.
        return result
    accepted = lambda r: bool(r['ranking']) and r['top_score'] >= threshold
    correct = lambda r: accepted(r) and r['ranking'][0] in r['positive_ids']
    false = [r for r in rows if accepted(r) and not correct(r)]
    result['acceptance'] = {
        'threshold':threshold,'accepted_queries':sum(accepted(r) for r in rows),
        'false_positive_count':len(false),
        'precision':(sum(correct(r) for r in rows)/sum(accepted(r) for r in rows)) if any(accepted(r) for r in rows) else None,
        'false_rejection_rate_on_known_queries':mean([int(not accepted(r)) for r in positives]),
        'wrong_accepted_known_queries':sum(accepted(r) and not correct(r) for r in positives),
        'false_positive_rate_on_no_match_queries':mean([int(accepted(r)) for r in negatives]),
        'no_match_rejection':mean([int(not accepted(r)) for r in negatives]),
        'correct_acceptance_recall':mean([int(correct(r)) for r in positives]),
        'false_negative_rate':mean([int(not correct(r)) for r in positives]),
        'false_negative_count':sum(not correct(r) for r in positives),
        'false_positive_query_ids':[r['query_id'] for r in false]}
    return result


def fit_threshold(rows):
    """Development only: maximize balanced correct acceptance / no-match rejection.

    Wrong accepted top results count as false positives even in positive queries.
    Conservative higher threshold wins exact objective ties. Never deploy this fit
    without evaluating the frozen value on independent instances.
    """
    if not any(r['positive_ids'] for r in rows) or not any(not r['positive_ids'] for r in rows):
        return {'status':'insufficient_data','threshold':None}
    scores=sorted({r['top_score'] for r in rows if r['ranking']})
    if not scores:
        return {'status':'insufficient_data','threshold':None}
    choices=[math.nextafter(scores[0],-math.inf),math.nextafter(scores[-1],math.inf)]
    choices.extend((a+b)/2 for a,b in zip(scores,scores[1:]))
    candidates=[]
    for threshold in choices:
        metrics=summarize(rows,threshold)['acceptance']
        objective=(metrics['correct_acceptance_recall']+metrics['no_match_rejection'])/2
        candidates.append((objective,threshold,metrics))
    objective,threshold,metrics=max(candidates,key=lambda r:(r[0],r[1]))
    return {'status':'development_fit_only','threshold':threshold,'balanced_objective':objective,'development_metrics':metrics}
