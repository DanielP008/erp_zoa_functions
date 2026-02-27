# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port 8080 for the Functions Framework
EXPOSE 8080

# Run the Functions Framework when the container launches
# --target refers to the function name in main.py
CMD ["functions-framework", "--target=main", "--port=8080", "--debug"]
