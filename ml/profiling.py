import os

import pandas as pd
import requests

URL_API = os.getenv("API_URL", "http://localhost:8000/avis")
response = requests.get(URL_API, timeout=60)
response.raise_for_status()
data = response.json()
df = pd.DataFrame(data["avis"])
print(df.shape)
