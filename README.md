# Medical Shop App (Flask + SQLite)

This is a simple medical shop inventory and billing web application built with Flask and SQLite.

## 🚀 Features
- Medicine inventory management
- Billing system with auto-fill from inventory
- Printable PDF invoice generation
- Schedule H/H1 tagging

## 📦 Project Structure
```
medical_shop_app/
├── app/                 # Flask app code (routes, models, templates)
├── run.py              # Entry point
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore list
└── README.md
```

## 🌐 Deploy on Render (Free Hosting)
1. Push this project to GitHub
2. Create a free account at [Render](https://render.com)
3. Click "New Web Service" → Connect GitHub repo
4. Fill in:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn run:app --bind 0.0.0.0:$PORT`
5. Deploy and access the live URL!

## ✅ Requirements
- Python 3.8+
- Flask

## 💡 Notes
- SQLite is fine for small apps. Consider PostgreSQL for larger deployments.

---