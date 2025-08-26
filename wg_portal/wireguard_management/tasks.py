import subprocess
from celery import shared_task
from .models import FirewallRule, WireGuardServer

def build_iptables_command(rule):
    """Повертає команду iptables для правила FirewallRule"""
    base = ["docker", "exec", "wireguard_vpn", "iptables"]
    if rule.action == 'allow':
        target = 'ACCEPT'
    elif rule.action == 'deny':
        target = 'DROP'
    else:
        target = 'ACCEPT'
    
    cmd = base + ['-A', 'FORWARD']
    if rule.source_ip:
        cmd += ['-s', rule.source_ip]
    if rule.destination_ip:
        cmd += ['-d', rule.destination_ip]
    if rule.protocol and rule.protocol != 'any':
        cmd += ['-p', rule.protocol]
    cmd += ['-j', target]
    return cmd

@shared_task
def apply_firewall_rules(server_id=None):
    """
    Застосовує всі правила FirewallRule для вказаного WireGuardServer (або для всіх)
    """
    print('START TASK')
    # 1. Очистити старі правила для FORWARD
    subprocess.run(["docker", "exec", "wireguard_vpn", "iptables", "-F", "FORWARD"])
    # 2. Встановити політику за замовчуванням DROP
    subprocess.run(["docker", "exec", "wireguard_vpn", "iptables", "-P", "FORWARD", "DROP"])
    # 3. Додати правила з БД (allow/deny)
    rules = FirewallRule.objects.filter(is_enabled=True)
    if server_id:
        rules = rules.filter(network__servers__id=server_id)
    print(f'Rules: {rules.count()}')
    import logging
    logger = logging.getLogger("firewall")
    for rule in rules.order_by('priority'):
        cmd = build_iptables_command(rule)
        result = subprocess.run(cmd, capture_output=True, text=True)
        msg = f"Applied firewall rule: {rule.name} (src={rule.source_ip}, action={rule.action})"
        if result.returncode == 0:
            logger.info(msg)
            print(msg)
        else:
            logger.error(f"FAILED: {msg} | {result.stderr}")
            print(f"FAILED: {msg} | {result.stderr}")
    return f"Applied {rules.count()} firewall rules."
