#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agregador de Notícias com NewsAPI
--------------------------------
Versão: 2.0
Deploy: Render
"""

import os
from flask import Flask, render_template, jsonify
import sqlite3
import datetime
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
import requests
from apscheduler.schedulers.background import BackgroundScheduler

class Config:
    """Configurações centralizadas do sistema"""
    
    # Configurações da API de Notícias
    NEWS_API_KEY = os.getenv('NEWS_API_KEY', "dcb23e470ef1442bb8b6a4a08def145e")
    NEWS_API_BASE_URL = "https://newsapi.org/v2/everything"
    
    # Configurações do banco de dados
    DATABASE = os.path.join(os.getcwd(), "noticias.db")
    
    # Configurações de conteúdo
    TOPICS = [
        "Política Brasil",
        "Economia",
        "Esportes",
        "Tecnologia",
        "Entretenimento",
        "Ciência",
        "Saúde",
        "Educação"
    ]
    NOTICIAS_POR_TOPICO = 5
    UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 30))  # minutos
    
    # Configurações de idioma e região
    LANGUAGES = ['pt', 'pt-BR']
    COUNTRY = 'br'
    
    # Configurações do sistema
    DEBUG = os.getenv('FLASK_ENV', 'development') == 'development'
    PORT = int(os.getenv('PORT', 5000))
    
    # Configurações de score
    BASE_SCORE = 1000.0
    RANDOM_FACTOR_MAX = 50
    TIME_WEIGHT = 0.7
    
    # Cores dos tópicos
    TOPIC_COLORS = {
        "Política Brasil": "rgba(255,0,0,0.7)",
        "Economia": "rgba(0,128,0,0.7)",
        "Esportes": "rgba(0,0,255,0.7)",
        "Tecnologia": "rgba(128,0,128,0.7)",
        "Entretenimento": "rgba(255,165,0,0.7)",
        "Ciência": "rgba(0,128,128,0.7)",
        "Saúde": "rgba(0,255,0,0.7)",
        "Educação": "rgba(128,0,0,0.7)"
    }

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
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
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
            
            for topic in Config.TOPICS:
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
        
        return render_template(
            'index.html',
            articles=articles,
            last_update=formatted_update,
            update_interval=Config.UPDATE_INTERVAL,
            topics=Config.TOPICS,
            topic_colors=Config.TOPIC_COLORS
        )
    except Exception as e:
        print(f"Erro na rota index: {e}")
        return "Erro ao carregar a página. Por favor, tente novamente."

@app.route("/api/articles")
def get_articles():
    """API endpoint para obter artigos em formato JSON"""
    try:
        articles = aggregator.db.get_articles()
        return jsonify([{
            'topic': art.topic,
            'title': art.title,
            'description': art.description,
            'url': art.url,
            'publishedAt': art.publishedAt,
            'score': art.score
        } for art in articles])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=aggregator.update_content,
        trigger="interval",
        minutes=Config.UPDATE_INTERVAL
    )
    scheduler.start()
    return scheduler

# Rota de health check para o Render
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    print("\n=== Iniciando Agregador de Notícias ===")
    print(f"API Key: {Config.NEWS_API_KEY}")
    print(f"Intervalo de atualização: {Config.UPDATE_INTERVAL} minutos")
    
    # Inicialização
    scheduler = init_scheduler()
    aggregator.update_content()  # Primeira atualização
    
    try:
        # Inicia o servidor Flask
        app.run(
            host='0.0.0.0',
            port=Config.PORT,
            debug=Config.DEBUG,
            use_reloader=False
        )
    except (KeyboardInterrupt, SystemExit):
        print("\n=== Encerrando aplicação ===")
        scheduler.shutdown()