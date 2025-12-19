#!/bin/bash
# Real-time monitoring of brain's autonomous activities

echo "🧠 Autonomous Brain Activity Monitor"
echo "===================================="
echo ""

tail -f autonomous_daemon.log | grep --line-buffered -E \
  "(identified.*needs|setting.*goals|executing.*goals|Goal [0-9]|Agent.*initialized|workflow|Implementation|modifications|features_added)" | \
  while read line; do
    if [[ $line == *"identified"* ]]; then
      echo -e "\n✨ $line"
    elif [[ $line == *"Goal"* ]]; then
      echo -e "🎯 $line"
    elif [[ $line == *"Agent"* ]]; then
      echo -e "🤖 $line"
    elif [[ $line == *"workflow"* ]]; then
      echo -e "⚙️  $line"
    else
      echo "   $line"
    fi
  done
