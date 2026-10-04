echo "Starting Claude in the Claude folder (v7.2)..."

if [ -d /Volumes/GIT ]; then
    cd /Volumes/GIT
elif [ -d /Users/tbrennan-marquez/GIT ]; then
    cd /Users/tbrennan-marquez/GIT
else
    echo "Neither /Volumes/GIT nor /GIT exists"
    return 1
fi

cd CLAUDE/SHARED_WORK_FOLDER
claude --continue --dangerously-skip-permissions --model opus
