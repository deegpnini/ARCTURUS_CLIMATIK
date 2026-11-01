import pytest
from datetime import datetime, timedelta, timezone
from model_runner import verificar_frescor

@pytest.mark.parametrize("minutos,esperado", [(5, False), (44, False), (46, True), (120, True), (-30, True)])
def test_fronteira_sem_fuso(minutos, esperado):
    assert verificar_frescor(datetime.now() - timedelta(minutes=minutos)) is esperado

def test_none_e_stale():
    assert verificar_frescor(None) is True

def test_timestamp_com_fuso():
    ts = datetime.now(timezone(timedelta(hours=-3))) - timedelta(minutes=10)
    assert verificar_frescor(ts) is False
