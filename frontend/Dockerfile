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

# Expose port
EXPOSE 3000

# Start the development server
CMD ["npm", "start"]