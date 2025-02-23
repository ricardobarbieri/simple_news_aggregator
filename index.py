#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agregador de Notícias com Google Trends e NewsAPI
-----------------------------------------------
"""

from dataclasses import dataclass
import sqlite3
import time
import datetime
import random
import os
from typing import List, Dict, Optional, Union
from flask import Flask, render_template_string
import requests
from apscheduler.schedulers.background import BackgroundScheduler

# Template HTML como uma constante global
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Agregador de Notícias - Tendências</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .news-card {
            height: 100%;
            transition: all 0.3s ease;
            border: none;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
        }
        .news-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }
        .score-badge {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }
        .topic-badge {
            position: absolute;
            top: 10px;
            left: 10px;
            background-color: rgba(0,123,255,0.9);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
        }
        .card-body { padding-top: 45px; }
        .navbar { box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card-title {
            font-size: 1.1em;
            font-weight: 600;
            line-height: 1.4;
        }
        .card-text {
            font-size: 0.9em;
            color: #666;
        }
        .update-info {
            font-size: 0.8em;
            color: #888;
        }
        .btn-primary {
            border-radius: 20px;
            padding: 8px 20px;
            font-size: 0.9em;
        }
        footer {
            background: #343a40;
            color: #fff;
            padding: 20px 0;
            margin-top: 50px;
        }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-newspaper me-2"></i>
                Agregador de Notícias
            </a>
            <span class="navbar-text">
                <i class="fas fa-sync-alt me-2"></i>
                Última atualização: {{ last_update }}
            </span>
        </div>
    </nav>
    
    <div class="container py-4">
        <div class="row mb-4">
            <div class="col">
                <h2><i class="fas fa-trending-up me-2"></i>Tendências e Notícias</h2>
                <p class="text-muted">
                    <i class="fas fa-clock me-2"></i>
                    Atualização automática a cada {{ update_interval }} minutos
                </p>
            </div>
        </div>
        
        {% if articles %}
        <div class="row g-4">
            {% for art in articles %}
            <div class="col-12 col-md-6 col-lg-4">
                <div class="news-card card">
                    <div class="card-body">
                        <span class="score-badge">
                            <i class="fas fa-star me-1"></i>
                            {{ "%.1f"|format(art.score) }}
                        </span>
                        <span class="topic-badge">
                            <i class="fas fa-hashtag me-1"></i>
                            {{ art.topic }}
                        </span>
                        <h5 class="card-title">{{ art.title }}</h5>
                        <p class="card-text">{{ art.description or '' }}</p>
                        <p class="card-text update-info">
                            <i class="far fa-clock me-1"></i>
                            {{ art.publishedAt }}
                        </p>
                        <a href="{{ art.url }}" target="_blank" class="btn btn-primary">
                            <i class="fas fa-external-link-alt me-1"></i>
                            Ler Mais
                        </a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            Nenhuma notícia disponível no momento.
        </div>
        {% endif %}
    </div>

    <footer class="bg-dark text-light">
        <div class="container text-center">
            <p class="mb-0">
                <i class="fas fa-code me-2"></i>
                Desenvolvido com Python, Flask e NewsAPI
            </p>
            <small class="text-muted">
                <i class="fas fa-sync me-2"></i>
                Próxima atualização em {{ update_interval }} minutos
            </small>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

class Config:
    """Configurações centralizadas do sistema"""
    NEWS_API_KEY = "dcb23e470ef1442bb8b6a4a08def145e"
    NEWS_API_BASE_URL = "https://newsapi.org/v2/everything"
    DATABASE = "noticias.db"
    NUM_TOP_TOPICS = 5
    NOTICIAS_POR_TOPICO = 3
    UPDATE_INTERVAL = 30
    LANGUAGES = ['pt', 'pt-BR']
    COUNTRY = 'br'
    DEBUG = True
    BASE_SCORE = 1000.0
    RANDOM_FACTOR_MAX = 50
    TIME_WEIGHT = 0.7

    # Lista de tópicos fixos para usar quando o Google Trends falhar
    DEFAULT_TOPICS = [
        "Política Brasil",
        "Economia",
        "Esportes",
        "Tecnologia",
        "Entretenimento"
    ]
    
@dataclass
class Article:
    """Classe de dados para representar um artigo/notícia"""
    id: Optional[int]
    topic: str
    title: str
    description: str
    url: str
    publishedAt: str
    score: float
    last_update: Union[str, datetime.datetime]

class Database:
    """Gerenciador do banco de dados SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    url TEXT NOT NULL,
                    publishedAt TEXT NOT NULL,
                    score REAL NOT NULL,
                    last_update TIMESTAMP NOT NULL
                )
            ''')

    def insert_article(self, article: Article):
        with self.get_connection() as conn:
            last_update = (
                article.last_update.isoformat() 
                if isinstance(article.last_update, datetime.datetime)
                else article.last_update
            )
            
            conn.execute('''
                INSERT INTO articles 
                (topic, title, description, url, publishedAt, score, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.topic,
                article.title,
                article.description,
                article.url,
                article.publishedAt,
                article.score,
                last_update
            ))

    def get_articles(self) -> List[Article]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM articles ORDER BY score DESC')
            rows = cursor.fetchall()
            articles = []
            for row in rows:
                row_dict = dict(row)
                row_dict.pop('id', None)
                
                if isinstance(row_dict['last_update'], str):
                    try:
                        row_dict['last_update'] = datetime.datetime.fromisoformat(
                            row_dict['last_update'].replace('Z', '+00:00')
                        )
                    except ValueError:
                        row_dict['last_update'] = datetime.datetime.now()
                
                articles.append(Article(id=None, **row_dict))
            return articles

    def clear_articles(self):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM articles')

class NewsService:
    """Serviço para buscar notícias da NewsAPI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_news_from_api(self, topic: str) -> List[Dict]:
        try:
            params = {
                'q': topic,
                'language': 'pt',
                'sortBy': 'relevancy',
                'pageSize': Config.NOTICIAS_POR_TOPICO,
                'apiKey': self.api_key
            }
            
            response = requests.get(
                Config.NEWS_API_BASE_URL,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                print(f"Encontradas {len(articles)} notícias para '{topic}'")
                return articles
            else:
                print(f"Erro na API: {data.get('message', 'Erro desconhecido')}")
                return []
                
        except Exception as e:
            print(f"Erro ao buscar notícias para '{topic}': {e}")
            return []

class NewsAggregator:
    """Agregador principal que coordena todos os serviços"""
    
    def __init__(self):
        self.db = Database(Config.DATABASE)
        self.news_service = NewsService(Config.NEWS_API_KEY)

    def calculate_score(self, publishedAt: str) -> float:
        try:
            pub_time = datetime.datetime.fromisoformat(
                publishedAt.replace('Z', '+00:00')
            )
        except Exception:
            pub_time = datetime.datetime.now()

        time_diff = (
            datetime.datetime.now(datetime.timezone.utc) - 
            pub_time.astimezone(datetime.timezone.utc)
        ).total_seconds() / 3600.0
        
        time_score = Config.BASE_SCORE * (1.0 / (1.0 + time_diff))
        random_factor = random.uniform(0, Config.RANDOM_FACTOR_MAX)
        final_score = (time_score * Config.TIME_WEIGHT + 
                      random_factor * (1 - Config.TIME_WEIGHT))
        
        return round(final_score, 2)

    def update_content(self):
        print(f"\n=== Iniciando atualização: {datetime.datetime.now()} ===")
        
        try:
            self.db.clear_articles()
            
            # Usando tópicos padrão em vez do Google Trends
            for topic in Config.DEFAULT_TOPICS:
                print(f"\nProcessando tópico: {topic}")
                articles = self.news_service.fetch_news_from_api(topic)
                
                for art in articles:
                    current_time = datetime.datetime.now()
                    article = Article(
                        id=None,
                        topic=topic,
                        title=art.get("title", "Sem título"),
                        description=art.get("description", ""),
                        url=art.get("url", "#"),
                        publishedAt=art.get("publishedAt", current_time.isoformat()),
                        score=self.calculate_score(art.get("publishedAt", "")),
                        last_update=current_time
                    )
                    self.db.insert_article(article)

            print("\n=== Atualização concluída com sucesso ===")
        except Exception as e:
            print(f"\nERRO durante atualização: {e}")

# Inicialização do Flask
app = Flask(__name__)
aggregator = NewsAggregator()

@app.route("/")
def index():
    try:
        articles = aggregator.db.get_articles()
        
        if articles:
            last_update = articles[0].last_update
            if isinstance(last_update, str):
                try:
                    last_update = datetime.datetime.fromisoformat(
                        last_update.replace('Z', '+00:00')
                    )
                except ValueError:
                    last_update = datetime.datetime.now()
            
            formatted_update = last_update.strftime("%d/%m/%Y às %H:%M:%S")
        else:
            formatted_update = "Nunca"
        
        return render_template_string(
            HTML_TEMPLATE,  # Usando o template global
            articles=articles,
            last_update=formatted_update,
            update_interval=Config.UPDATE_INTERVAL
        )
    except Exception as e:
        print(f"Erro na rota index: {e}")
        return "Erro ao carregar a página. Por favor, tente novamente."

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=aggregator.update_content,
        trigger="interval",
        minutes=Config.UPDATE_INTERVAL
    )
    scheduler.start()
    return scheduler

if __name__ == "__main__":
    print("\n=== Iniciando Agregador de Notícias ===")
    print(f"API Key: {Config.NEWS_API_KEY}")
    print(f"Intervalo de atualização: {Config.UPDATE_INTERVAL} minutos")
    
    # Inicialização
    scheduler = init_scheduler()
    aggregator.update_content()  # Primeira atualização
    
    try:
        # Inicia o servidor Flask
        app.run(debug=Config.DEBUG, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        print("\n=== Encerrando aplicação ===")
        scheduler.shutdown()    