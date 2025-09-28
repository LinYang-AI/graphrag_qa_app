FROM node:18-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Create build directory and set permissions
RUN mkdir -p node_modules/.cache && chmod -R 777 node_modules/.cache

# Expose port (different from user frontend)
EXPOSE 3001

# Set environment variable for admin interface
ENV REACT_APP_ADMIN_MODE=true
ENV REACT_APP_API_URL=http://localhost:8000

# Start the development server
CMD ["npm", "start"]