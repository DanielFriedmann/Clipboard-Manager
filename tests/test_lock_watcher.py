from lock_watcher import CHECK_INTERVAL, LockWatcher


class FakeWidget:
    def __init__(self):
        self.scheduled = []

    def after(self, delay, callback):
        self.scheduled.append((delay, callback))


def make(idle=0, locked=False, minutes=15, follow=True):
    state = {"idle": idle, "locked": locked, "calls": 0}
    settings = {"lock_minutes": minutes, "lock_on_windows_lock": follow}

    def on_lock():
        state["calls"] += 1

    watcher = LockWatcher(FakeWidget(), on_lock, settings,
                          get_idle=lambda: state["idle"], is_locked=lambda: state["locked"])
    return watcher, state, settings


def test_locks_after_idle_time():
    watcher, state, _settings = make(idle=14 * 60)
    assert not watcher.should_lock()
    state["idle"] = 15 * 60
    assert watcher.should_lock()


def test_never_means_never():
    watcher, _state, _settings = make(idle=10 * 3600, minutes=0)
    assert not watcher.should_lock()


def test_windows_lock_only_when_enabled():
    watcher, _state, settings = make(locked=True, follow=False)
    assert not watcher.should_lock()
    settings["lock_on_windows_lock"] = True    # Einstellung wirkt sofort
    assert watcher.should_lock()


def test_tick_calls_lock_and_keeps_checking():
    watcher, state, _settings = make(locked=True)
    watcher.start()
    delay, tick = watcher.widget.scheduled[-1]
    assert delay == CHECK_INTERVAL
    tick()
    assert state["calls"] == 1
    assert len(watcher.widget.scheduled) == 2   # nächste Prüfung ist geplant


def test_keeps_checking_after_error():
    watcher, _state, _settings = make()
    watcher._get_idle = lambda: 1 / 0
    watcher.start()
    try:
        watcher.widget.scheduled[-1][1]()
    except ZeroDivisionError:
        pass
    assert len(watcher.widget.scheduled) == 2