"""Hand-written products for the two categories DummyJSON does not have.

Prices are already in INR. For books the "brand" field holds the author,
so the recommender can learn "more by the same author".
Fields: (title, brand, description, price_inr, discount_percent, stock, rating)
"""

BOOKS = [
    ("Atomic Habits", "James Clear",
     "A practical guide to building good habits and breaking bad ones through tiny "
     "daily improvements. Explains habit stacking, environment design and the "
     "habit loop with real-life examples. Self-help bestseller.", 499, 22, 64, 4.8),
    ("The Psychology of Money", "Morgan Housel",
     "Short stories about how people think about money, greed, risk and happiness. "
     "Personal finance lessons on saving, investing and long-term wealth.", 399, 18, 48, 4.7),
    ("Rich Dad Poor Dad", "Robert T. Kiyosaki",
     "Classic personal finance book contrasting two attitudes to money, assets and "
     "liabilities. Encourages financial literacy and investing early.", 349, 15, 52, 4.5),
    ("The Alchemist", "Paulo Coelho",
     "A fable-like novel about a shepherd boy who travels from Spain to Egypt "
     "following his dream. Fiction about destiny, courage and listening to your heart.", 299, 10, 70, 4.6),
    ("Wings of Fire", "A. P. J. Abdul Kalam",
     "Autobiography of India's Missile Man and former President, from his childhood "
     "in Rameswaram to leading India's space and missile programmes. Inspiring memoir.", 299, 12, 58, 4.8),
    ("Ikigai: The Japanese Secret to a Long and Happy Life", "Hector Garcia",
     "Explores the Japanese idea of ikigai, a reason for being, through interviews "
     "with long-lived people in Okinawa. Self-help on purpose, health and happiness.", 399, 20, 45, 4.4),
    ("Clean Code", "Robert C. Martin",
     "A programming handbook on writing readable, maintainable software. Covers "
     "naming, functions, comments, error handling, unit tests and refactoring.", 899, 10, 30, 4.7),
    ("Introduction to Algorithms", "Thomas H. Cormen",
     "The standard computer science textbook on algorithms and data structures: "
     "sorting, graphs, dynamic programming, greedy methods and complexity analysis.", 1299, 8, 22, 4.6),
    ("Hands-On Machine Learning with Scikit-Learn and TensorFlow", "Aurelien Geron",
     "Practical machine learning book with Python code. Covers regression, "
     "classification, clustering, K-Means, neural networks and deep learning.", 1599, 12, 26, 4.8),
    ("Python Crash Course", "Eric Matthes",
     "Beginner-friendly programming book that teaches Python from scratch, then "
     "builds a game, data visualisations and a Django web application.", 899, 15, 40, 4.7),
    ("The White Tiger", "Aravind Adiga",
     "Booker Prize winning Indian novel told by a driver from a small village who "
     "rises in Delhi and Bangalore. Darkly funny fiction about class and ambition.", 349, 10, 35, 4.3),
    ("The God of Small Things", "Arundhati Roy",
     "Booker Prize winning Indian novel about twins growing up in Kerala and the "
     "family secrets that shape their lives. Lyrical literary fiction.", 399, 10, 33, 4.4),
    ("Sapiens: A Brief History of Humankind", "Yuval Noah Harari",
     "Big-picture history of the human species, from hunter-gatherers to the "
     "agricultural and scientific revolutions. Popular non-fiction.", 499, 20, 50, 4.6),
    ("Deep Work", "Cal Newport",
     "Productivity book about focusing without distraction on cognitively demanding "
     "tasks. Rules for studying, working and learning hard skills quickly.", 399, 15, 38, 4.5),
    ("Harry Potter and the Philosopher's Stone", "J. K. Rowling",
     "The first book in the Harry Potter fantasy series: an orphan discovers he is a "
     "wizard and starts school at Hogwarts. Fiction for children and adults.", 399, 10, 75, 4.9),
    ("The Pragmatic Programmer", "David Thomas",
     "Classic programming book of practical advice for software developers: "
     "debugging, automation, testing, design and career habits.", 999, 10, 24, 4.7),
]

TOYS = [
    ("Rainbow Wooden Stacking Tower", "TinyTinker",
     "Seven smooth wooden rings in rainbow colours that stack on a peg. Builds "
     "hand-eye coordination for toddlers. Non-toxic paint, ages 1+.", 549, 15, 40, 4.5),
    ("RC Off-Road Monster Truck 1:16", "WonderWheels",
     "Remote control monster truck with big rubber tyres, 2.4 GHz controller and "
     "rechargeable battery. Climbs ramps and grass. Ages 6+.", 1899, 25, 18, 4.3),
    ("City Builder Brick Set 500 Pieces", "BrickBuddy",
     "Construction brick set with 500 pieces to build houses, shops and vehicles. "
     "Compatible with popular brick brands. Creative building toy, ages 6+.", 1499, 20, 26, 4.6),
    ("Magnetic Building Tiles 60 Pieces", "BrickBuddy",
     "Colourful magnetic tiles that click together into 3D shapes, towers and cars. "
     "STEM building toy that teaches geometry. Ages 3+.", 2299, 18, 20, 4.7),
    ("Plush Teddy Bear 40 cm", "CuddleCo",
     "Extra soft brown teddy bear with a satin bow. Huggable soft toy, washable and "
     "safe for children. Great birthday gift.", 699, 10, 55, 4.6),
    ("Volcano and Crystal Science Kit", "SparkLab",
     "Kids science experiment kit: build an erupting volcano and grow your own "
     "crystals. Includes guide book and safety goggles. STEM learning, ages 8+.", 899, 15, 30, 4.4),
    ("Classic Wooden Chess Set", "PlayNest",
     "Folding wooden chess board with hand-carved pieces stored inside. Strategy "
     "board game for kids and adults.", 799, 12, 34, 4.5),
    ("Junior Doctor Pretend Play Kit", "PlayNest",
     "Role-play doctor set with stethoscope, thermometer, syringe and carry case. "
     "Pretend play toy for imaginative kids, ages 3+.", 599, 20, 42, 4.3),
    ("Jigsaw Puzzle 1000 Pieces: Monuments of India", "PuzzleCraft",
     "1000-piece jigsaw puzzle featuring the Taj Mahal, India Gate and Hawa Mahal. "
     "Thick pieces, poster included. Family puzzle game.", 699, 10, 28, 4.4),
    ("360 Degree Stunt RC Car", "WonderWheels",
     "Double-sided remote control stunt car that flips and spins 360 degrees with "
     "LED lights. Rechargeable, ages 6+.", 1299, 22, 24, 4.2),
    ("Build and Code Robot Kit", "SparkLab",
     "Build a robot and program it with a block-based coding app. Teaches coding, "
     "sensors and motors. STEM robotics kit, ages 10+.", 3499, 15, 12, 4.6),
    ("Musical Baby Activity Cube", "TinyTinker",
     "Five-sided activity cube with piano keys, animal sounds, shape sorter and "
     "lights. Baby and toddler learning toy, ages 1+.", 999, 18, 30, 4.5),
    ("Watercolour Paint and Craft Set", "ArtSprout",
     "Art kit with watercolours, brushes, crayons, sketch pens and drawing pad in a "
     "carry case. Arts and crafts for kids, ages 5+.", 499, 15, 46, 4.4),
    ("Foam Dart Blaster with 20 Darts", "WonderWheels",
     "Soft foam dart blaster with a 10-dart clip and 20 darts. Outdoor action toy "
     "for safe play, ages 8+.", 899, 20, 25, 4.2),
    ("Trade Tycoon Family Board Game", "PlayNest",
     "Property trading board game: buy cities, collect rent and become the "
     "richest player. Family board game for 2-6 players, ages 8+.", 799, 15, 32, 4.4),
    ("Kinetic Play Sand 1 kg with Moulds", "ArtSprout",
     "Mess-free moldable play sand with six shape moulds and a tray. Sensory play "
     "toy that never dries out, ages 3+.", 649, 12, 38, 4.5),
]
