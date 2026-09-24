import shlex

from app import ssh

_URL = "https://pkgs.tailscale.com/stable/tailscale_latest_amd64.tgz"


def _pasta_shell(pasta: str) -> str:
    if pasta == "~" or pasta.startswith("~/"):
        return '"$HOME"' + shlex.quote(pasta[1:]) if pasta != "~" else '"$HOME"'
    return shlex.quote(pasta)


def gerar_script(pasta: str, auth_key: str, hostname: str) -> str:
    d = _pasta_shell(pasta)
    return f"""set -e
D={d}
mkdir -p "$D/state"
cd "$D"
D=$(pwd -P)
trap 'rm -f "$D/.authkey"' EXIT
if [ ! -x "$D/tailscaled" ]; then
  curl -fsSL -o ts.tgz {_URL}
  tar xzf ts.tgz --strip-components=1
  rm -f ts.tgz
fi
if ! pgrep -u "$USER" -x tailscaled >/dev/null; then
  nohup setsid "$D/tailscaled" --tun=userspace-networking --state="$D/state/tailscaled.state" --socket="$D/tailscaled.sock" > "$D/tailscaled.log" 2>&1 < /dev/null &
  sleep 4
fi
( umask 077; printf %s {shlex.quote(auth_key)} > "$D/.authkey" )
"$D/tailscale" --socket="$D/tailscaled.sock" up --auth-key=file:"$D/.authkey" --hostname={shlex.quote(hostname)}
rm -f "$D/.authkey"
B=$(printf %s "$D" | base64 | tr -d '\\n')
LINHA='@reboot D=$(echo '"$B"' | base64 -d); nohup setsid "$D/tailscaled" --tun=userspace-networking --state="$D/state/tailscaled.state" --socket="$D/tailscaled.sock" >> "$D/tailscaled.log" 2>&1 < /dev/null &'
( crontab -l 2>/dev/null | grep -v -- '--tun=userspace-networking' || true ; echo "$LINHA" ) | crontab -
"$D/tailscale" --socket="$D/tailscaled.sock" status
"$D/tailscale" --socket="$D/tailscaled.sock" ip -4
"""


def preparar(cli, pasta, auth_key, hostname, ao_receber) -> int:
    canal = cli.get_transport().open_session()
    canal.set_combine_stderr(True)
    canal.exec_command("bash -s")
    canal.sendall(gerar_script(pasta, auth_key, hostname).encode())
    canal.shutdown_write()
    return ssh.ler_canal(canal, ao_receber)
