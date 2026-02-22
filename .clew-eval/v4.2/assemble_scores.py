#!/usr/bin/env python3
"""Assemble scores.json from individual scorer files."""
import json, re, os

scores_dir = '/Users/albertgwo/Repositories/clew/.clew-eval/v4.2/scores'
tests = {}

for test_id in ['A1','A2','A3','A4','B1','B2','C1','C2','E1','E2','E3','E4']:
    tests[test_id] = {}
    for scorer_num in [1, 2]:
        fname = f'{test_id}-scorer{scorer_num}.txt'
        path = os.path.join(scores_dir, fname)
        with open(path) as f:
            content = f.read().strip()

        scorer_key = f'scorer_{scorer_num}'
        tests[test_id][scorer_key] = {}

        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.match(
                r'Agent (Alpha|Beta):\s*Discovery=(\d),\s*Precision=(\d),\s*Completeness=(\d),\s*Relational=(\d),\s*Confidence=(\d)',
                line
            )
            if m:
                agent = m.group(1).lower()
                tests[test_id][scorer_key][agent] = {
                    'discovery': int(m.group(2)),
                    'precision': int(m.group(3)),
                    'completeness': int(m.group(4)),
                    'relational': int(m.group(5)),
                    'confidence': int(m.group(6)),
                }
            else:
                print(f'WARNING: Could not parse line in {fname}: {line}')

result = {'tests': tests}
out_path = os.path.join(scores_dir, 'scores.json')
with open(out_path, 'w') as f:
    json.dump(result, f, indent=2)

print(f'Wrote scores.json with {len(tests)} tests')

# Validate
for tid, scorers in tests.items():
    for sk, agents in scorers.items():
        if 'alpha' not in agents or 'beta' not in agents:
            print(f'ERROR: {tid}/{sk} missing alpha or beta')
        for agent_name, dims in agents.items():
            if len(dims) != 5:
                print(f'ERROR: {tid}/{sk}/{agent_name} has {len(dims)} dims')
print('Validation complete')
