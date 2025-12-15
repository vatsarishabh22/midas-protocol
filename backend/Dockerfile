# 1. Base Image: Start with a lightweight version of Python 3.10
FROM python:3.10-slim

# 2. Working Directory: Create a folder named '/app' inside the container
WORKDIR /app

# 3. Dependencies: Copy just the requirements file first
COPY requirements.txt .

# 4. Install: Run pip to install libraries (no cache saves space)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Code: Copy all your backend files into the container
COPY . .

# 6. Port: Tell Docker we intend to listen on port 7860
EXPOSE 7860

# Run the app
CMD ["python", "application.py"]