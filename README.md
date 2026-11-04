# BIS Taxi


A taxi app for Almaty, built by our team as a course project for Basics of Information Systems.

Passengers choose where to go, compare prices across four tariffs, and pay in cash or through Kaspi. The nearest free driver gets the order and has 30 seconds to accept it. After the ride, both sides rate each other. An admin approves new drivers and can see all rides.

This is a student project, so the Kaspi payment is only simulated: no real money moves.

## Team

| Name | Student ID |
| --- | --- |
| Ilyas Amzekhan | 24B031647 |
| Aruzhan Nagizbekova | 24B031916 |
| Amir Bakhytzhan | 24B031694 |
| Aknur Abdimailk | 24B032174 |
| Yenglik Aman | 24B031635 |

## Before you start

You'll need:

- [uv](https://docs.astral.sh/uv/) for Python
- [Node.js](https://nodejs.org/) 20 or newer
- [Docker Desktop](https://www.docker.com/products/docker-desktop/), running. We use it only for the map routes.
- [osmium-tool](https://osmcode.org/osmium-tool/): `brew install osmium-tool` on a Mac

## Run it

Clone the repo and open it in a terminal. The first setup takes a few minutes, because it downloads the map of Kazakhstan and cuts out Almaty.

**1. Set up the backend**

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
DEMO_PASSWORD=change-me-please uv run python scripts/seed.py
```

**2. Start the route server**

```bash
scripts/osrm_prepare.sh
docker compose -f infra/osrm/docker-compose.yml up -d
```

**3. Start the backend**

```bash
uv run uvicorn --factory taxi_service.main:create_app --port 8000
```

**4. Start the website** (in a second terminal)

```bash
cd frontend
npm ci
npm run dev
```

Now open <http://localhost:5173>.

Next time, you only need steps 3 and 4. Just make sure Docker Desktop is open.

## Try a ride

Log in with one of the demo accounts. The password is the one you set in step 1.

| Who | Username |
| --- | --- |
| Passenger | `demo_passenger_1` |
| Driver | `demo_driver_1` |
| Admin | `demo_admin` |

To see a full ride, you need both sides at once:

1. Open a private window, log in as `demo_driver_1`, and go online.
2. In your normal window, log in as `demo_passenger_1`, pick a destination, choose the Economy tariff, and order.
3. Accept the order in the driver window and take the ride through to the end.

The app is built for phones first. On a computer, it looks best in your browser's device view.

**Good to know:** the Kaspi option only shows up if you add a Kaspi link to `.env`, and "Continue with Google" only shows up if you add a Google client ID. Everything else works without them.


## More

Want the technical details? See the [developer guide](docs/development.md) (in Russian).
