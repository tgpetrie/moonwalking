PORTS ?= 5001 5173

nuke:
	./scripts/kill_dev_procs.sh || true
	./scripts/kill_ports.sh $(PORTS)

dev:
	./scripts/dev_all.sh

dev-back:
	./scripts/dev_backend.sh

dev-front:
	./scripts/dev_frontend.sh

smoke:
	./scripts/smoke_frontend.sh
