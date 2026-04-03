#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="install.log"
PYTHON_MIN_VERSION="3.9"

get_python_cmd() {
    if command -v python &>/dev/null; then
        echo "python"
        return
    fi

    if command -v python3 &>/dev/null; then
        echo "python3"
        return
    fi

    return 1
}

get_pip_cmd() {
    if command -v pip &>/dev/null; then
        echo "pip"
        return
    fi

    if command -v pip3 &>/dev/null; then
        echo "pip3"
        return
    fi

    return 1
}

apt_install() {
    sudo apt-get update -y
    sudo apt-get install -y "$@"
}

log() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$LOG_FILE"
}

version_gte() {
    local installed="$1"
    local required="$2"
    printf '%s\n%s' "$required" "$installed" | sort -V -C
}

install_docker() {
    if command -v docker &>/dev/null; then
        log "Docker вже встановлено: $(docker --version)"
        return
    fi

    if ! command -v curl &>/dev/null; then
        log "curl відсутній, встановлюю curl..."
        apt_install curl
    fi

    log "Встановлення Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    log "Docker встановлено: $(docker --version)"
}

install_docker_compose() {
    if command -v docker-compose &>/dev/null; then
        log "Docker Compose вже встановлено: $(docker-compose --version)"
        return
    fi

    if docker compose version &>/dev/null; then
        log "Docker Compose доступний як docker compose: $(docker compose version --short)"
        return
    fi

    if ! command -v curl &>/dev/null; then
        log "curl відсутній, встановлюю curl..."
        apt_install curl
    fi

    log "Встановлення Docker Compose..."
    local compose_version
    compose_version=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -Po '"tag_name": "\K[^"]+')
    sudo curl -L "https://github.com/docker/compose/releases/download/${compose_version}/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log "Docker Compose встановлено: $(docker-compose --version)"
}

install_python() {
    local python_cmd
    if python_cmd=$(get_python_cmd); then
        local installed_version
        installed_version=$("$python_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if version_gte "$installed_version" "$PYTHON_MIN_VERSION"; then
            log "Python вже встановлено: $($python_cmd --version)"
            return
        fi
        log "Python $installed_version < $PYTHON_MIN_VERSION — оновлення..."
    fi
    log "Встановлення Python $PYTHON_MIN_VERSION+..."
    apt_install python3 python3-dev python-is-python3
    python_cmd=$(get_python_cmd)
    log "Python встановлено: $($python_cmd --version)"
}

install_pip() {
    local pip_cmd
    if pip_cmd=$(get_pip_cmd); then
        log "pip вже встановлено: $($pip_cmd --version)"
        return
    fi
    log "Встановлення pip..."
    apt_install python3-pip
    pip_cmd=$(get_pip_cmd)
    log "pip встановлено: $($pip_cmd --version)"
}

python_module_exists() {
    local module_name="$1"
    local python_cmd
    python_cmd=$(get_python_cmd)
    "$python_cmd" -c "import ${module_name}" &>/dev/null
}

python_module_version() {
    local module_name="$1"
    local version_expr="$2"
    local python_cmd
    python_cmd=$(get_python_cmd)
    "$python_cmd" -c "import ${module_name}; print(${version_expr})" 2>/dev/null || echo "невідома"
}

install_python_packages() {
    local pip_cmd
    pip_cmd=$(get_pip_cmd)
    local packages=(
        "torch:torch:torch.__version__"
        "torchvision:torchvision:torchvision.__version__"
        "pillow:PIL:PIL.__version__"
        "django:django:django.__version__"
    )

    for package_spec in "${packages[@]}"; do
        IFS=":" read -r package_name module_name version_expr <<<"$package_spec"

        if python_module_exists "$module_name"; then
            local ver
            ver=$(python_module_version "$module_name" "$version_expr")
            log "$package_name вже встановлено (версія: $ver)"
        else
            log "Встановлення $package_name..."
            "$pip_cmd" install --quiet "$package_name"
            local ver
            ver=$(python_module_version "$module_name" "$version_expr")
            log "$package_name встановлено (версія: $ver)"
        fi
    done
}

print_versions() {
    local docker_compose_version="не знайдено"
    if command -v docker-compose &>/dev/null; then
        docker_compose_version=$(docker-compose --version)
    elif docker compose version &>/dev/null; then
        docker_compose_version=$(docker compose version --short)
    fi

    local python_version="не знайдено"
    if python_cmd=$(get_python_cmd 2>/dev/null); then
        python_version=$($python_cmd --version 2>/dev/null || echo "не знайдено")
    fi

    local pip_version="не знайдено"
    if pip_cmd=$(get_pip_cmd 2>/dev/null); then
        pip_version=$($pip_cmd --version 2>/dev/null || echo "не знайдено")
    fi

    log "--- Перевірка версій ---"
    log "Docker:         $(docker --version 2>/dev/null || echo 'не знайдено')"
    log "Docker Compose: $docker_compose_version"
    log "Python:         $python_version"
    log "pip:            $pip_version"
    log "torch:          $(python_module_version 'torch' 'torch.__version__')"
    log "torchvision:    $(python_module_version 'torchvision' 'torchvision.__version__')"
    log "pillow:         $(python_module_version 'PIL' 'PIL.__version__')"
    log "django:         $(python_module_version 'django' 'django.__version__')"
    log "--- Готово ---"
}

main() {
    log "=== Початок налаштування середовища ==="
    install_docker
    install_docker_compose
    install_python
    install_pip
    install_python_packages
    print_versions
    log "=== Середовище готове ==="
}

main
