# Start with Python
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# 1. Copy requirements (Relative to current folder, no 'backend/' prefix)
COPY requirements.txt .

# 2. Install dependencies
# Added --no-cache-dir to keep image size small
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of the code (Current folder -> /app)
COPY . .

# 4. Run the application
# Note: application:app works because application.py is now at /app/application.py
CMD ["uvicorn", "application:app", "--host", "0.0.0.0", "--port", "7860"]