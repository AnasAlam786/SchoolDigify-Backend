from pathlib import Path

path = Path(r"c:/Users/Falak/OneDrive/Desktop/Python Projects/SchoolDigify/src/view/templates/admit_card/admit_card.html")
text = path.read_text()
text = text.replace('bg-gray-700/50', 'bg-gray-800/50').replace('bg-gray-700/30', 'bg-gray-800/30').replace('hover:bg-gray-700/40', 'hover:bg-gray-800/40')
path.write_text(text)
print('colors replaced')
