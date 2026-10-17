# Helper fragment; not a complete Tiger strategy.
# initialize: set context.qqq, context.tqqq, context.days and context.pending=[].
# Each daily callback: check_orders, update signal, then rebalance.
# Keep set_max_leverage consistent with the user's borrowing constraint.
# Reference prices must already be available at submission time.
# Defaults are case-specific; adjust reserve and limit settings explicitly.
import math


def check_orders(context):
    waiting = []
    for req_id in context.pending:
        ticket = get_order(req_id)
        if ticket is None:
            raise ValueError('Missing order: ' + str(req_id))
        if ticket.status == 6:
            if context.days <= 5:
                log.info('FILL|%s|%s|%s|%s' % (req_id, ticket.dt, ticket.filled, ticket.filled_price))
        elif ticket.status == 4:
            log.info('CANCELLED|' + str(req_id))
        elif ticket.status == 8:
            message = 'REJECTED|%s|%s' % (req_id, ticket.reason)
            log.info(message)
            raise ValueError(message)
        elif ticket.status in [5, 9]:
            # Cancellation is asynchronous: keep tracking until terminal status.
            cancel_order(req_id)
            waiting.append(req_id)
            log.info('CANCEL_REQUEST|%s|status=%s' % (req_id, ticket.status))
        else:
            raise ValueError("Unknown order status: " + str(ticket.status))
    context.pending = waiting


def held_amount(context, code):
    holding = context.portfolio.positions.get(code)
    if holding is None:
        return 0
    return int(holding.amount)


def rebalance(context, q_open, t_open, weight, invested=0.995,
              fee_reserve=20.0, limit_buffer=0.01):
    if not math.isfinite(weight):
        raise ValueError("Invalid target weight")
    if weight < 0:
        raise ValueError("Invalid target weight")
    if weight > 1:
        raise ValueError("Invalid target weight")
    if not math.isfinite(invested):
        raise ValueError("Invalid invested fraction")
    if invested <= 0:
        raise ValueError("Invalid invested fraction")
    if invested > 1:
        raise ValueError("Invalid invested fraction")
    if not math.isfinite(fee_reserve):
        raise ValueError("Invalid fee reserve")
    if fee_reserve < 0:
        raise ValueError("Invalid fee reserve")
    if not math.isfinite(limit_buffer):
        raise ValueError("Invalid limit buffer")
    if limit_buffer < 0:
        raise ValueError("Invalid limit buffer")
    for price in [q_open, t_open]:
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid reference price")
    if len(context.pending) > 0:
        log.info('WAIT_FOR_ORDER_CONFIRMATION')
        return 0
    q_amount = held_amount(context, 'QQQ')
    t_amount = held_amount(context, 'TQQQ')
    if min(q_amount, t_amount) < 0:
        raise ValueError('Unexpected short holding')
    cash = float(context.portfolio.cash)
    if not math.isfinite(cash):
        raise ValueError('Invalid account cash')
    equity = cash + q_amount*q_open + t_amount*t_open
    if equity <= 0:
        raise ValueError('Invalid account equity')
    if cash < -0.01:
        raise ValueError('Negative cash; review fills and fees')
    targets = [int(equity*invested*(1-weight)/q_open),
               int(equity*invested*weight/t_open)]
    changes = [targets[0]-q_amount, targets[1]-t_amount]
    assets = [context.qqq, context.tqqq]
    selling = False
    for i in range(2):
        if changes[i] < 0:
            req_id = order(assets[i], changes[i])
            if req_id is None:
                raise ValueError('Sell order creation failed')
            context.pending.append(req_id)
            selling = True
    if selling:
        return 0
    # Never budget with proceeds from an unfilled sell.
    available = max(0.0, cash-max(fee_reserve, equity*(1-invested)))
    caps = [q_open*(1+limit_buffer), t_open*(1+limit_buffer)]
    needed = [max(0, changes[0]), max(0, changes[1])]
    required = needed[0]*caps[0] + needed[1]*caps[1]
    if required <= 0:
        return 0
    scale = min(1.0, available/required)
    for i in range(2):
        quantity = int(needed[i]*scale)
        quantity = min(quantity, int(available/caps[i]))
        if quantity > 0:
            req_id = order(assets[i], quantity, style='limit', limit_price=caps[i])
            if req_id is None:
                raise ValueError('Buy order creation failed')
            context.pending.append(req_id)
            available -= quantity*caps[i]
