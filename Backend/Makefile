# =============================================================================
# Makefile — OpenCapacity Backend
#
# Comandos rapidos para gestionar el entorno Docker (dev y produccion).
# Uso: make <target>   |   make help  para ver todos los comandos
# =============================================================================

# Detectar docker compose v2 (plugin moderno) o v1 (standalone legacy)
COMPOSE        := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_DEV    := $(COMPOSE) -f docker-compose.yml
COMPOSE_PROD   := $(COMPOSE) -f docker-compose.prod.yml

# Numero de workers al escalar  (uso: make scale-workers N=3)
N ?= 2

.PHONY: help \
        up down restart rebuild reload stop start \
        logs logs-api logs-worker logs-redis logs-db logs-flower \
        ps stats \
        shell-api shell-worker shell-redis shell-db \
        scale-workers \
        prod-up prod-down prod-rebuild prod-logs prod-ps \
        clean prune \
        test

# Target por defecto
.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# Ayuda
# -----------------------------------------------------------------------------
help:
	@echo ""
	@echo "  OpenCapacity Backend — Comandos disponibles"
	@echo ""
	@echo "  ── DESARROLLO ──────────────────────────────────────────────────"
	@echo "  make up              Levantar todos los servicios en background"
	@echo "  make down            Detener y eliminar contenedores"
	@echo "  make restart         Reiniciar todos los servicios"
	@echo "  make rebuild         Reconstruir imagenes y levantar"
	@echo "  make reload          Forzar recreacion completa de contenedores"
	@echo "  make stop            Detener sin eliminar contenedores"
	@echo "  make start           Iniciar contenedores detenidos"
	@echo ""
	@echo "  ── LOGS ────────────────────────────────────────────────────────"
	@echo "  make logs            Seguir todos los logs en tiempo real"
	@echo "  make logs-api        Seguir logs de la API FastAPI"
	@echo "  make logs-worker     Seguir logs del worker Celery"
	@echo "  make logs-redis      Seguir logs de Redis"
	@echo "  make logs-db         Seguir logs de PostgreSQL"
	@echo "  make logs-flower     Seguir logs de Flower (monitor Celery)"
	@echo ""
	@echo "  ── STATUS ──────────────────────────────────────────────────────"
	@echo "  make ps              Estado de los contenedores"
	@echo "  make stats           Uso de CPU/RAM en tiempo real"
	@echo ""
	@echo "  ── SHELLS ──────────────────────────────────────────────────────"
	@echo "  make shell-api       Bash dentro del contenedor API"
	@echo "  make shell-worker    Bash dentro del contenedor worker"
	@echo "  make shell-redis     Redis-CLI interactivo"
	@echo "  make shell-db        PSQL interactivo"
	@echo ""
	@echo "  ── WORKERS ─────────────────────────────────────────────────────"
	@echo "  make scale-workers N=3   Escalar a N replicas del worker"
	@echo ""
	@echo "  ── PRODUCCION ──────────────────────────────────────────────────"
	@echo "  make prod-up         Levantar entorno de produccion"
	@echo "  make prod-down       Detener produccion"
	@echo "  make prod-rebuild    Reconstruir y levantar produccion"
	@echo "  make prod-logs       Seguir logs de produccion"
	@echo "  make prod-ps         Estado de contenedores en produccion"
	@echo ""
	@echo "  ── LIMPIEZA ────────────────────────────────────────────────────"
	@echo "  make clean           Eliminar contenedores y volumenes (dev)"
	@echo "  make prune           Limpiar recursos Docker huerfanos"
	@echo ""
	@echo "  ── TESTS ───────────────────────────────────────────────────────"
	@echo "  make test            Ejecutar suite de pruebas pytest"
	@echo ""

# -----------------------------------------------------------------------------
# Desarrollo
# -----------------------------------------------------------------------------

up:
	$(COMPOSE_DEV) up -d
	@echo ""
	@echo "  Servicios levantados:"
	@echo "    API:    http://localhost:8000/api/v1/docs"
	@echo "    Flower: http://localhost:5555"
	@echo ""

down:
	$(COMPOSE_DEV) down

restart:
	$(COMPOSE_DEV) restart

rebuild:
	$(COMPOSE_DEV) up -d --build

reload:
	$(COMPOSE_DEV) up -d --build --force-recreate

stop:
	$(COMPOSE_DEV) stop

start:
	$(COMPOSE_DEV) start

# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------

logs:
	$(COMPOSE_DEV) logs -f

logs-api:
	$(COMPOSE_DEV) logs -f api

logs-worker:
	$(COMPOSE_DEV) logs -f worker

logs-redis:
	$(COMPOSE_DEV) logs -f redis

logs-db:
	$(COMPOSE_DEV) logs -f postgres

logs-flower:
	$(COMPOSE_DEV) logs -f flower

# -----------------------------------------------------------------------------
# Status
# -----------------------------------------------------------------------------

ps:
	$(COMPOSE_DEV) ps

stats:
	docker stats

# -----------------------------------------------------------------------------
# Shells interactivos
# -----------------------------------------------------------------------------

shell-api:
	$(COMPOSE_DEV) exec api bash

shell-worker:
	$(COMPOSE_DEV) exec worker bash

shell-redis:
	$(COMPOSE_DEV) exec redis redis-cli

shell-db:
	$(COMPOSE_DEV) exec postgres psql -U postgres -d hosting_capacity

# -----------------------------------------------------------------------------
# Escalar workers
# -----------------------------------------------------------------------------

scale-workers:
	$(COMPOSE_DEV) up -d --scale worker=$(N)
	@echo "Workers escalados a $(N) replicas."

# -----------------------------------------------------------------------------
# Produccion
# -----------------------------------------------------------------------------

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

prod-rebuild:
	$(COMPOSE_PROD) up -d --build

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-ps:
	$(COMPOSE_PROD) ps

# -----------------------------------------------------------------------------
# Limpieza
# -----------------------------------------------------------------------------

clean:
	$(COMPOSE_DEV) down -v --remove-orphans
	@echo "Contenedores y volumenes de desarrollo eliminados."

prune:
	docker system prune -f
	@echo "Recursos Docker no usados eliminados."

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

test:
	$(COMPOSE_DEV) exec api pytest tests/ -v
