const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('ordering', this.value);
            window.location.href = url.toString();
        });
    }

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const url = new URL(window.location.href);
                if (this.value.trim()) {
                    url.searchParams.set('search', this.value);
                } else {
                    url.searchParams.delete('search');
                }
                url.searchParams.delete('page');
                window.location.href = url.toString();
            }
        });
    }

    function resetFilters() {
        window.location.href = "/content_team/";
    }

    const searchOffcanvas = document.getElementById('search_offcanvas');
    if (searchOffcanvas && searchInput) {
        searchOffcanvas.addEventListener('input', function() {
            searchInput.value = this.value;
        });
        searchInput.addEventListener('input', function() {
            searchOffcanvas.value = this.value;
        });
    }

    document.querySelectorAll('.team-card').forEach((card, index) => {
        card.style.animationDelay = '0.1s';
        card.style.opacity = '1';
    });

    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function() {
            sessionStorage.setItem('scrollPosition', window.scrollY);
        });
    }

    window.addEventListener('load', function() {
        const scrollPosition = sessionStorage.getItem('scrollPosition');
        if (scrollPosition) {
            window.scrollTo(0, parseInt(scrollPosition));
            sessionStorage.removeItem('scrollPosition');
        }
    });