# 🚀 Quick Start Commands

Copy and paste these into Terminal (Cmd+Space → Terminal).

---

## First time setup (run once)
```bash
source ~/.zshrc
```

---

## Launch Streamlit Dashboard
```bash
cd ~/AgenticHub/second-brain && source ~/.zshrc && PYTHONPATH=. streamlit run streamlit/app.py
```
Then open: http://localhost:8501

---

## Add sample places (test data)
```bash
cd ~/AgenticHub/second-brain && source ~/.zshrc && PYTHONPATH=. sbpy -c "
from second_brain.places import save
save('Nagarjuna Restaurant', 'Bangalore', 'India', 'Restaurant', 'Best Andhra biryani, try the thali', 5, tags=['indian','biryani','must-visit'])
save('Blue Tokai Coffee', 'Delhi', 'India', 'Cafe', 'Great specialty coffee, good wifi', 4, tags=['coffee','wifi','cafe'])
save('Tsukiji Market', 'Tokyo', 'Japan', 'Market', 'Fresh sushi for breakfast, arrive early', 5, tags=['sushi','market','seafood'])
print('Done! Refresh Streamlit.')
"
```

---

## Ingest a URL
```bash
cd ~/AgenticHub/second-brain && source ~/.zshrc && PYTHONPATH=. sbpy scripts/ingest.py url https://example.com --tag research
```

## Ingest a PDF
```bash
cd ~/AgenticHub/second-brain && source ~/.zshrc && PYTHONPATH=. sbpy scripts/ingest.py pdf ~/Downloads/file.pdf --tag financial
```

## Query your brain
```bash
cd ~/AgenticHub/second-brain && source ~/.zshrc && PYTHONPATH=. sbpy scripts/query.py "your question here"
```

---

## Git — pull latest code
```bash
cd ~/AgenticHub/second-brain && git pull
```
