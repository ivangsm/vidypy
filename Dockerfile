# Base image with Python and FFmpeg
FROM python:3.12-alpine

# Install FFmpeg
RUN apk update && apk add --no-cache ffmpeg poetry

# Set the working directory in the container
WORKDIR /app

# Copy the poetry files
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry install --no-root --without dev

# Copy the application code
COPY . /app

# Set up a volume for the directory where user_data.db will be created
VOLUME /app/data

# Run the application
CMD ["poetry", "run", "python", "vidypy/main.py"]
