from handlers import captcha, start, earn, bonus, profile, promo, withdraw, tasks, top, games, admin, botohub, duel, search, lottery, wheel, cases, battlepass

routers = [
    captcha.router,  # must be first: catches all input while captcha is active (FSM state)
    botohub.router,
    start.router,
    earn.router,
    bonus.router,
    profile.router,
    promo.router,
    withdraw.router,
    tasks.router,
    battlepass.router,
    top.router,
    games.router,
    lottery.router,
    duel.router,
    search.router,
    wheel.router,
    cases.router,
    admin.router,
]

__all__ = ["routers"]
