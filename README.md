# AusNepal Visa Analytics — Backend

Django REST Framework API serving Australian student visa analytics for Nepali applicants, sourced from official Department of Home Affairs data.

**Live API:** https://australia-nepal-visa-analytics.onrender.com

## Features
- Overview, trends, comparison, and forecast endpoints
- Grant rate, application volume, and demographic breakdowns
- Education sector and university market analytics
- CSV/Excel upload pipeline for data refreshes

## Tech stack
- Django 5 + Django REST Framework
- PostgreSQL (hosted on Neon)
- pandas / openpyxl for data processing
- Deployed on Render

## Frontend
Consumed by a React/Vite dashboard — see [aus-visa-insight](https://github.com/Riyamkafle/aus-visa-insight)

## Local development
\`\`\`bash
pip install -r requirements.txt --break-system-packages
python manage.py migrate
python manage.py runserver
\`\`\`

Requires a \`.env\` with \`DEBUG\`, \`SECRET_KEY\`, \`DB_*\`, \`ALLOWED_HOSTS\`, \`CORS_ALLOWED_ORIGINS\`.
