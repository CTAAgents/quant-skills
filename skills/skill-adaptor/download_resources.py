"""
下载论文和GitHub源码
"""
import os
import sys
import requests
import subprocess


def download_file(url, output_path):
    """下载文件"""
    print(f"正在下载: {url}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"下载成功: {output_path}")
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False


def clone_github_repo(repo_url, output_dir):
    """克隆GitHub仓库"""
    print(f"正在克隆仓库: {repo_url}")
    try:
        # 使用浅克隆，只获取最新版本
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, output_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"克隆成功: {output_dir}")
            return True
        else:
            print(f"克隆失败: {result.stderr}")
            # 如果git不可用，至少创建一个说明文件
            with open(os.path.join(output_dir, "README_SOURCE.md"), "w", encoding="utf-8") as f:
                f.write(f"GitHub 仓库: {repo_url}\n")
                f.write("请手动访问上述URL获取源码\n")
            return False
    except Exception as e:
        print(f"克隆失败: {e}")
        return False


def main():
    """主函数"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    references_dir = os.path.join(base_dir, "references")
    
    # 创建目录（如果不存在）
    os.makedirs(references_dir, exist_ok=True)
    
    # 1. 下载论文PDF
    paper_url = "https://arxiv.org/pdf/2606.01311.pdf"
    paper_output = os.path.join(references_dir, "SkillAdaptor_paper.pdf")
    download_file(paper_url, paper_output)
    
    # 2. 下载论文摘要页面作为参考
    abs_url = "https://arxiv.org/abs/2606.01311"
    abs_output = os.path.join(references_dir, "SkillAdaptor_abstract.html")
    download_file(abs_url, abs_output)
    
    # 3. 克隆GitHub仓库
    repo_url = "https://github.com/zjunlp/SkillAdaptor.git"
    repo_dir = os.path.join(references_dir, "SkillAdaptor_github")
    
    # 如果目录已存在，先删除
    if os.path.exists(repo_dir):
        print(f"目录已存在，正在删除: {repo_dir}")
        try:
            import shutil
            shutil.rmtree(repo_dir)
        except Exception as e:
            print(f"删除失败: {e}")
    
    clone_github_repo(repo_url, repo_dir)
    
    print("\n=== 资源下载完成 ===")


if __name__ == "__main__":
    main()
