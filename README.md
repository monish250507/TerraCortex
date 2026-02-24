# TerraCortex - AEGIS Environmental Monitoring System

An advanced environmental monitoring system that tracks air quality, weather conditions, and generates AI-powered insights for public health advisories.

## Features

- Real-time environmental data collection
- AI-powered risk assessment using Claude 3.5 Sonnet
- Government dashboard for monitoring and control
- Public advisory system
- Automated alerting system
- Historical trend analysis

## Prerequisites

- Python 3.8+
- API keys for:
  - OpenAQ (for air quality data)
  - OpenWeatherMap (for weather data)
  - OpenRouter (for Claude AI access)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd terracortex
   ```

2. Navigate to the backend directory:
   ```bash
   cd backend
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your actual API keys to the `.env` file

5. Run the application:
   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
   ```

## API Keys Setup

To run this application, you need to obtain API keys from the following services:

1. **OpenAQ API Key**: Sign up at https://openaq.org/
2. **OpenWeatherMap API Key**: Sign up at https://openweathermap.org/api
3. **OpenRouter API Key**: Sign up at https://openrouter.ai/ for access to Claude 3.5 Sonnet

Store these keys in the `.env` file as shown in `.env.example`.

## Usage

- Government/Admin Interface: http://127.0.0.1:8001/admin/aegis_admin_2026
- Public Advisory Page: http://127.0.0.1:8001/public
- Main Application: http://127.0.0.1:8001/

Default credentials for admin access:
- Username: admin
- Password: aegis_admin_2026

## Security Note

The `.env` file containing API keys is excluded from version control by `.gitignore`. Never commit actual API keys to the repository.