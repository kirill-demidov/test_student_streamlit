# Use Python base image
FROM python:3.12

# Set the working directory inside the container
WORKDIR /app

# Copy everything from the current directory to the container
COPY . .



# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the environment variable inside the container
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/creds.json"

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Run the Streamlit app
CMD streamlit run app.py --server.port 8080 --server.address 0.0.0.0 --server.headless true