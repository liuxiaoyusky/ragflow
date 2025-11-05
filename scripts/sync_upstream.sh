#!/bin/bash
# RAGFlow 上游同步脚本
# 按照文档流程执行与上游的同步操作

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查前置条件
check_prerequisites() {
    log_info "检查前置条件..."
    
    # 检查Git
    if ! command -v git &> /dev/null; then
        log_error "Git未安装"
        exit 1
    fi
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose未安装"
        exit 1
    fi
    
    # 检查upstream远程仓库
    if ! git remote | grep -q upstream; then
        log_error "未找到upstream远程仓库，请先配置：git remote add upstream https://github.com/infiniflow/ragflow.git"
        exit 1
    fi
    
    # 检查备份目录
    if [ ! -d "$HOME/backup" ]; then
        log_error "备份目录不存在: $HOME/backup"
        exit 1
    fi
    
    log_info "前置条件检查完成"
}

# 步骤1：数据库快照备份
backup_database() {
    log_info "步骤1: 执行数据库备份..."
    
    if [ -f "scripts/backup_database.sh" ]; then
        ./scripts/backup_database.sh
        log_info "数据库备份完成"
    else
        log_error "备份脚本不存在: scripts/backup_database.sh"
        exit 1
    fi
}

# 步骤2：同步上游基准分支
sync_upstream_branch() {
    log_info "步骤2: 同步上游基准分支..."
    
    # 切换到upstream-main分支
    git checkout upstream-main
    
    # 拉取上游最新更新
    git pull upstream main
    
    log_info "上游基准分支同步完成"
}

# 步骤3：Rebase同步本地化分支
rebase_main_branch() {
    log_info "步骤3: Rebase同步本地化分支..."
    
    # 切换到main分支
    git checkout main
    
    # 基于upstream-main分支执行Rebase
    if git rebase upstream-main; then
        log_info "Rebase成功完成"
    else
        log_error "Rebase过程中出现冲突，请手动解决冲突后继续"
        log_info "解决冲突后执行: git add <冲突文件> && git rebase --continue"
        log_info "或者放弃Rebase: git rebase --abort"
        exit 1
    fi
}

# 步骤4：服务部署与功能测试
deploy_and_test() {
    log_info "步骤4: 服务部署与功能测试..."
    
    # 停止当前服务
    log_info "停止当前服务..."
    docker-compose down 2>/dev/null || docker compose down 2>/dev/null || log_warn "未找到运行中的服务"
    
    # 启动服务
    log_info "启动服务..."
    if [ -f "docker/docker-compose.yml" ]; then
        cd docker
        docker-compose up -d
        cd ..
    elif [ -f "docker-compose.yml" ]; then
        docker-compose up -d
    else
        log_error "未找到docker-compose.yml文件"
        exit 1
    fi
    
    log_info "等待服务启动..."
    sleep 30
    
    # 检查服务状态
    log_info "检查服务状态..."
    if docker ps | grep -q ragflow; then
        log_info "服务启动成功"
    else
        log_error "服务启动失败"
        exit 1
    fi
    
    log_info "请手动执行以下功能测试："
    log_info "1. 检查所有容器是否正常启动 (docker ps)"
    log_info "2. 访问本地化配置的端口，确认服务可正常访问"
    log_info "3. 测试知识库上传、检索、问答等基础功能"
    log_info "4. 测试硅基流动海外版接口调用、本地化Fix相关功能"
    log_info "5. 检查既往知识库数据、配置数据是否完整"
}

# 步骤5：记录维护日志
create_maintenance_log() {
    log_info "步骤5: 创建维护日志..."
    
    LOG_DIR="logs"
    mkdir -p "$LOG_DIR"
    
    LOG_FILE="$LOG_DIR/maintenance_log_$(date +%Y%m%d).md"
    
    # 如果日志文件不存在，创建模板
    if [ ! -f "$LOG_FILE" ]; then
        cat > "$LOG_FILE" << 'EOF'
# RAGFlow 维护日志

## 维护记录

| 同步日期 | 上游版本 | 操作人 | 冲突情况 | 测试结果 | 异常情况 |
|----------|----------|--------|----------|----------|----------|
EOF
    fi
    
    # 获取当前信息
    SYNC_DATE=$(date +%Y-%m-%d)
    UPSTREAM_VERSION=$(git rev-parse upstream-main 2>/dev/null || echo "未知")
    OPERATOR=$(whoami)
    
    # 添加新记录
    echo "| $SYNC_DATE | $UPSTREAM_VERSION | $OPERATOR | 待填写 | 待填写 | 无 |" >> "$LOG_FILE"
    
    log_info "维护日志已创建: $LOG_FILE"
    log_info "请编辑日志文件，填写冲突情况和测试结果"
}

# 主函数
main() {
    log_info "开始执行RAGFlow上游同步流程..."
    
    # 检查前置条件
    check_prerequisites
    
    # 步骤1：数据库备份
    backup_database
    
    # 步骤2：同步上游基准分支
    sync_upstream_branch
    
    # 步骤3：Rebase同步本地化分支
    rebase_main_branch
    
    # 步骤4：服务部署与功能测试
    deploy_and_test
    
    # 步骤5：创建维护日志
    create_maintenance_log
    
    log_info "RAGFlow上游同步流程执行完成！"
    log_info "请执行功能测试并更新维护日志"
}

# 执行主函数
main "$@"
