import pandas as pd

df = pd.read_json("data/raw_logs.json")

print(df.columns)