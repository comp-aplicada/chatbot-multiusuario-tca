from app.llm.personas import PERSONAS


def test_chaves_do_contrato():
    assert set(PERSONAS) == {"geral", "juridico"}


def test_prompts_terminam_com_no_think():
    assert all(prompt.endswith("/no_think") for prompt in PERSONAS.values())


def test_juridico_lembra_que_nao_substitui_advogado():
    assert "não substitui" in PERSONAS["juridico"]
    assert "advogado" in PERSONAS["juridico"]
