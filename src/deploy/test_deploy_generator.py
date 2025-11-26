import re
from deploy_generator import DeployStageGenerator


def test_simple_template_uses_port_and_tag():
    config = {"port": 3000}
    gen = DeployStageGenerator(config, use_compose=False)
    yaml_str = gen.get_output_string()

    # 1. Проверяем, что это джоба deploy_production со stage deploy
    assert "deploy_production:" in yaml_str
    assert "stage: deploy" in yaml_str

    # 2. Проверяем, что подставился порт
    assert "3000:3000" in yaml_str
    assert "http://$SSH_HOST:3000" in yaml_str

    # 3. Проверяем, что используется CI_COMMIT_SHA как тег
    assert '$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA' in yaml_str


def test_compose_template_uses_port_and_not_direct_run():
    config = {"port": 8080}
    gen = DeployStageGenerator(config, use_compose=True)
    yaml_str = gen.get_output_string()

    # 1. Это тоже deploy_production
    assert "deploy_production:" in yaml_str
    assert "stage: deploy" in yaml_str

    # 2. Проверяем, что порт подставился в URL
    assert "http://$SSH_HOST:8080" in yaml_str

    # 3. Проверяем, что есть docker compose команды
    assert "docker compose pull" in yaml_str
    assert "docker compose up -d" in yaml_str

    # 4. В compose-режиме не должно быть прямого docker run app -p ...
    assert "docker run -d --name app" not in yaml_str
