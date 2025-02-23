document.addEventListener('DOMContentLoaded', function() {
    // Elementos
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const topicFilter = document.getElementById('topicFilter');
    const newsContainer = document.getElementById('newsContainer');
    const newsItems = document.querySelectorAll('.news-item');

    // Função de busca
    function filterNews() {
        const searchTerm = searchInput.value.toLowerCase();
        const selectedTopic = topicFilter.value.toLowerCase();

        newsItems.forEach(item => {
            const title = item.querySelector('.card-title').textContent.toLowerCase();
            const description = item.querySelector('.card-text').textContent.toLowerCase();
            const topic = item.dataset.topic.toLowerCase();

            const matchesSearch = title.includes(searchTerm) || description.includes(searchTerm);
            const matchesTopic = !selectedTopic || topic === selectedTopic;

            item.style.display = (matchesSearch && matchesTopic) ? 'block' : 'none';
        });
    }

    // Event listeners
    searchButton.addEventListener('click', filterNews);
    searchInput.addEventListener('keyup', filterNews);
    topicFilter.addEventListener('change', filterNews);

    // Compartilhamento
    document.querySelectorAll('.share-twitter').forEach(button => {
        button.addEventListener('click', function() {
            const url = this.dataset.url;
            const title = this.dataset.title;
            window.open(
                `https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`,
                'twitter-share',
                'width=550,height=400'
            );
        });
    });

    document.querySelectorAll('.share-facebook').forEach(button => {
        button.addEventListener('click', function() {
            const url = this.dataset.url;
            window.open(
                `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
                'facebook-share',
                'width=550,height=400'
            );
        });
    });

    document.querySelectorAll('.share-whatsapp').forEach(button => {
        button.addEventListener('click', function() {
            const url = this.dataset.url;
            const title = this.dataset.title;
            window.open(
                `https://api.whatsapp.com/send?text=${encodeURIComponent(title + ' ' + url)}`,
                'whatsapp-share',
                'width=550,height=400'
            );
        });
    });

    // Atualização automática do tempo
    function updateTimeAgo() {
        document.querySelectorAll('.update-info').forEach(element => {
            const date = new Date(element.dataset.date);
            const now = new Date();
            const diff = Math.floor((now - date) / 1000);

            let timeAgo;
            if (diff < 60) {
                timeAgo = `${diff} segundos atrás`;
            } else if (diff < 3600) {
                timeAgo = `${Math.floor(diff / 60)} minutos atrás`;
            } else if (diff < 86400) {
                timeAgo = `${Math.floor(diff / 3600)} horas atrás`;
            } else {
                timeAgo = `${Math.floor(diff / 86400)} dias atrás`;
            }

            element.textContent = timeAgo;
        });
    }

    // Atualiza o tempo a cada minuto
    setInterval(updateTimeAgo, 60000);
    updateTimeAgo();
});