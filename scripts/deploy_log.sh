#!/usr/bin/env bash
# use $1 for providing old deployed version. script get part of changelog from the beggining until old version

commit_msg=$(git log -n 1 --pretty=format:"%s" 2>&1)
commit_branch=$(git rev-parse --abbrev-ref --symbolic-full-name HEAD 2>&1)

if [[ $commit_msg == version* ]];
then
    if [[ -z "$1" ]];
    then
        # changelog from the beggining until first empty line
        sed -n "/version/,/^$/{/^$/q;p;}" CHANGELOG.md
    else
        # changelog from the beggining until provided string in changelog
        sed -n "/version/,/${1}/{/${1}/q; p;}" CHANGELOG.md
    fi
    exit
fi

# get log from git history. Use branch to master history
git log origin/master..HEAD --pretty=format:"*%s* by %an"
# if master is current branch log will be empty; add last commit
log=$(git log origin/master..HEAD 2>&1)
if [[ -z $log ]];
then
    git log -n 1 --pretty=format:"*%s* by %an"
fi
