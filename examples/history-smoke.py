def initialize(context):
    context.asset = symbol("QQQ")
    set_benchmark(context.asset)


def handle_data(context, data):
    history = data.history(
        context.asset,
        "close",
        5,
        "1d"
    )
    log.info(
        "QQQ latest historical close: %s"
        % history.iloc[-1]
    )
