# Start with Python
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# 1. Copy requirements from the 'backend' folder
COPY backend/requirements.txt .

# 2. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of the backend code into the container
COPY backend/ .

# 4. Run the application
# We use port 7860 because that's what Hugging Face expects
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]