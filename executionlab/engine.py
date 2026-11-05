"""Single-symbol replay. All policies decide after observing an event.

Market children are IOC at the first later event after latency. Passive
children queue behind displayed depth and fill only on later eligible prints.
This is a transparent simulator, not an exchange matching-engine replica.
"""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Event:
    t: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    trade_price: float
    trade_size: float
    aggressor: str

    @property
    def mid(self):
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class Config:
    quantity: float = 1000
    side: str = "buy"
    latency: float = 1
    participation: float = .1
    fee_bps: float = .5
    impact_bps: float = 2
    queue_multiplier: float = 1
    passive_ttl: float = 30

    def validate(self):
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        for k, v in asdict(self).items():
            if k != "side" and (not math.isfinite(v) or v < 0):
                raise ValueError(f"{k} must be finite and nonnegative")
        if self.quantity <= 0 or not 0 < self.participation <= 1 or self.passive_ttl <= 0:
            raise ValueError("positive quantity/TTL and participation in (0,1] required")


def validate_events(events):
    if len(events) < 2:
        raise ValueError("At least two events required")
    previous = -math.inf
    for e in events:
        if any(not math.isfinite(v) for k, v in asdict(e).items() if k != "aggressor"):
            raise ValueError("Nonfinite event value")
        if e.t <= previous or e.bid <= 0 or e.ask < e.bid:
            raise ValueError("Events must have strictly increasing timestamps and valid quotes")
        if min(e.bid_size, e.ask_size, e.trade_size) < 0 or e.trade_price <= 0:
            raise ValueError("Invalid price or size")
        if e.aggressor not in ("buy", "sell", "none") or (e.trade_size > 0 and e.aggressor == "none"):
            raise ValueError("Trade aggressor must be buy or sell for positive volume")
        previous = e.t


POLICIES = ("immediate", "twap", "pov", "passive")


def simulate(events, policy, config=Config()):
    config.validate()
    validate_events(events)
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    c = config
    sign = 1 if c.side == "buy" else -1
    arrival, terminal = events[0].mid, events[-1].mid
    start, end = events[0].t, events[-1].t
    filled = 0.0
    seen_volume = 0.0
    pending = None
    fills, audit, curve = [], [], []

    def log(e, action, **kw):
        audit.append(dict(t=e.t, action=action, **kw))

    def fill(e, q, price, kind, decision_t):
        nonlocal filled
        q = min(q, c.quantity - filled)
        if q <= 1e-9:
            return
        fee = q * price * c.fee_bps / 10000
        fills.append(dict(t=e.t, decision_t=decision_t, quantity=q, price=price,
                          fee=fee, kind=kind, mid=e.mid))
        filled += q
        log(e, "fill", quantity=q, price=price, kind=kind)

    for i, e in enumerate(events):
        # Process outstanding orders before using this event for decisions.
        if pending and e.t > pending["decision_t"] and e.t >= pending["ready"]:
            if pending["kind"] == "market":
                depth = e.ask_size if sign == 1 else e.bid_size
                q = min(pending["quantity"], depth)
                touch = e.ask if sign == 1 else e.bid
                impact = c.impact_bps * q / depth if depth else 0
                price = touch * (1 + sign * impact / 10000)
                if price <= 0:
                    raise ValueError("Impact assumption produces nonpositive price")
                fill(e, q, price, "market", pending["decision_t"])
                log(e, "ioc_expired", quantity=pending["quantity"] - q)
                pending = None
            else:
                if not pending["active"]:
                    pending["active"] = True
                    # Activation event's print cannot fill a newly resting order.
                    # If the submitted limit crosses now, cancel (post-only model).
                    crosses = (sign == 1 and pending["limit"] >= e.ask) or (sign == -1 and pending["limit"] <= e.bid)
                    if crosses:
                        log(e, "post_only_reject")
                        pending = None
                    else:
                        at_touch = abs(pending["limit"] - (e.bid if sign == 1 else e.ask)) < 1e-8
                        pending["queue"] = c.queue_multiplier * (e.bid_size if sign == 1 else e.ask_size)
                        # Away from touch, depth is unknown: retain conservative queue proxy.
                        log(e, "resting", limit=pending["limit"], queue=pending["queue"], at_touch=at_touch)
                elif e.t >= pending["expiry"]:
                    log(e, "cancel", quantity=pending["quantity"])
                    pending = None
                else:
                    eligible = ((sign == 1 and e.aggressor == "sell" and e.trade_price <= pending["limit"])
                                or (sign == -1 and e.aggressor == "buy" and e.trade_price >= pending["limit"]))
                    if eligible:
                        consumed = min(e.trade_size, pending["queue"])
                        pending["queue"] -= consumed
                        q = min(e.trade_size - consumed, pending["quantity"])
                        fill(e, q, pending["limit"], "passive", pending["decision_t"])
                        pending["quantity"] -= q
                        if pending["quantity"] < 1e-9:
                            pending = None
        seen_volume += e.trade_size
        curve.append(dict(t=e.t, filled=filled, mid=e.mid))
        if i == len(events) - 1 or filled >= c.quantity - 1e-9 or pending:
            continue
        remaining = c.quantity - filled
        if policy == "immediate":
            desired = remaining
        elif policy == "twap":
            # Time schedule uses a supplied horizon, never future volume/prices.
            desired = max(0, c.quantity * (e.t - start) / (end - start) - filled)
        elif policy == "pov":
            desired = max(0, c.participation * seen_volume - filled)
        else:
            desired = remaining
        if desired <= 1e-9:
            continue
        pending = dict(quantity=min(desired, remaining), decision_t=e.t,
                       ready=e.t + c.latency, kind="limit" if policy == "passive" else "market")
        if policy == "passive":
            pending.update(limit=e.bid if sign == 1 else e.ask, active=False,
                           queue=0, expiry=e.t + c.latency + c.passive_ttl)
        log(e, "submit", **pending)
    if pending:
        log(events[-1], "horizon_cancel", quantity=pending["quantity"])
    notional = sum(f["quantity"] * f["price"] for f in fills)
    fees = sum(f["fee"] for f in fills)
    execution = sign * (notional - filled * arrival)
    opportunity = sign * (c.quantity - filled) * (terminal - arrival)
    shortfall = execution + fees + opportunity
    denom = c.quantity * arrival
    volume = sum(e.trade_size for e in events)
    vwap = sum(e.trade_size * e.trade_price for e in events) / volume if volume else None
    summary = dict(policy=policy, side=c.side, target=c.quantity, filled=filled,
                   fill_pct=100 * filled / c.quantity, arrival=arrival, terminal=terminal,
                   average_price=notional / filled if filled else None, fees=fees,
                   execution_cost=execution, opportunity_cost=opportunity,
                   shortfall=shortfall, shortfall_bps=shortfall / denom * 10000,
                   market_vwap=vwap,
                   vs_vwap_bps=(sign * (notional / filled - vwap) / vwap * 10000 if filled and vwap else None),
                   cash_flow=-sign * notional - fees, inventory_change=sign * filled)
    return dict(summary=summary, config=asdict(c), fills=fills, audit=audit, curve=curve)
