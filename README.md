# Topic Modeling on Research Titles with BERTopic and MLOps

## Description
This project is an end-to-end implementation of a machine learning pipeline that performs topic modeling on thousands of research article titles collected from academic repositories such as IEEE. The goal is to automatically cluster and label groups of article titles using Natural Language Processing (NLP) techniques, making it easier to explore and understand large-scale academic content.

At its core, this project utilizes:

  1 K-Means Clustering to group article titles based on textual similarity,

  2 BERTopic, a transformer-based topic modeling technique, to assign interpretable topic names to each cluster,

  3 A robust text preprocessing pipeline using spaCy and NLTK,

  4 BeautifulSoup/Selenium or public APIs to scrape and collect research titles at scale,

  5 And a scalable MLOps architecture, including:

      - Reproducible model training pipelines,

      - Version control of data and models using DVC,

      - Model tracking via MLflow,

      - And deployment of the final model as a REST API using FastAPI and containerized with Docker.

## Project Structure

```
.
├── app/                      # FastAPI application
│   ├── main.py               # Main application entry point
│   └── api/                  # API endpoints
│       └── scrapping_service.py  # Web scraping service
│
├── data/                     # Data storage
│   ├── cleaned/              # Preprocessed and cleaned data
│   └── raw/                  # Original scraped data
│       ├── clustered/        # Data organized by topic clusters
│       └── TF-IDF/           # Feature vectors for modeling
│
├── logs/                     # Application and model training logs
│
├── mlruns/                   # Mlflow directory logs
│
├── src/                      # Source code
│   ├── data-cleaning/        # Data preprocessing
│   │   └── preprocessing.py  # Text preprocessing functions
│   ├── exploratory/          # Exploratory data analysis
│   │   └── EDA.ipynb         # Jupyter notebook for EDA
│   ├── modelling/            # Topic modeling implementation
│   │   └── TopicModelling.py # Topic modeling code
│   └── scrapping/            # Web scraping utilities
│       ├── getLinks.py       # Script to collect article links
│       └── getTitle.py       # Script to extract article titles
│
├── Dockerfile                # Docker configuration
└── requirements.txt          # Project dependencies
```

## How to Run

### Prerequisites
- Python 3.7+
- Docker (optional)

### Setup and Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Topic-Modelling-Article-Titles.git
cd Topic-Modelling-Article-Titles
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
# Without Docker
cd app
uvicorn main:app --reload

# With Docker
docker build -t topic-modelling-app .
docker run -p 8000:8000 topic-modelling-app
```

### Running the Topic Modeling Pipeline

1. To scrape new article data:
```bash
python src/scrapping/getLinks.py
python src/scrapping/getTitle.py
```

2. To process the data:
```bash
python src/data-cleaning/preprocessing.py
```

3. To run the topic modeling:
```bash
python src/modelling/TopicModelling.py
```

## Sample Output

When running the topic modeling process, you'll get a set of clusters with article titles grouped by topic. Here's an example output:

```
Topic 1: Machine Learning Applications
- "Convolutional Neural Networks for Image Recognition"
- "Deep Learning Approaches to Natural Language Processing"
- "Reinforcement Learning in Robotics"

Topic 2: Computer Security
- "Intrusion Detection Systems for IoT Networks"
- "Blockchain-based Authentication Mechanisms"
- "Privacy Preservation in Cloud Computing"

Topic 3: Data Management
- "Big Data Analytics for Business Intelligence"
- "NoSQL Database Performance Evaluation"
- "Data Warehousing in Healthcare Systems"
```

The API also provides endpoints to:
- Get topics from a new article title
- Browse articles by topic
- Search for related articles by similarity

Access the API documentation at http://localhost:8000/docs after running the application.

