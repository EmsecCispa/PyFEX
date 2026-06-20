def cli():
    pass


if __name__ == '__main__':
    try:
        cli()
    except KeyboardInterrupt:
        logging.debug("Exiting due to KeyboardInterrupt...")
