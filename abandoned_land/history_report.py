"""输出对局记录中的动作频率和释放前状态，辅助调参。"""

import argparse
import json
from collections import Counter


def main() -> None:
    parser = argparse.ArgumentParser(description="分析遗弃之地主线运行记录")
    parser.add_argument("path", nargs="?", default="run_history.jsonl")
    args = parser.parse_args()
    actions = Counter()
    reasons = Counter()
    rows = 0
    with open(args.path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            if row.get("event") == "action" and row.get("decision"):
                actions[row["decision"]] += 1
                reasons[row.get("reason", "")] += 1
    print(f"记录行数: {rows}")
    print("动作次数:")
    for name, count in actions.most_common():
        print(f"  {name}: {count}")
    print("释放原因:")
    for reason, count in reasons.most_common(10):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
