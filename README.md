# stopcovid-lambdas

## Architecture

See [architecture overview](docs/README.md).

## The simulator

You can simulate the core of dialog processing on the command line — by feeding the dialog engine with command-line entries rather than entries from a kinesis stream. Try it out by running `python simulator.py`.

## Deployment
Deployments are done via AWS CodeBuild. Log in to the CodeBuild UI to deploy dev and prod.

## CI
We use [black](https://black.readthedocs.io/en/stable/) for code formatting and flake8 for linting, with a custom rule setting maximum line length to 100.
- `black --config black.toml .`
- `flake8`



## Local development
There are a series of [sample events](sample_events/) in the project. You can run them against dev:
- `serverless invoke local -f sendMessage -p sample_events/send_message.json`

Run `docker-compose up` in the `db_local` directory