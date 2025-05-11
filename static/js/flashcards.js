const flashcards = JSON.parse(document.getElementById('flashcards-data').textContent);
let currentCard = 0;
let currentSet = [...flashcards];

// Function to get 30 random cards
function getRandomCards(cards, count = 30) {
    let shuffled = [...cards].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, Math.min(count, cards.length));
}

// Initialize with 30 random cards
currentSet = getRandomCards(flashcards);

// Update card display
function showCard(index) {
    if (currentSet.length === 0) return;
    
    const frontContent = document.querySelector('.flashcard-front .card-content');
    const backContent = document.querySelector('.flashcard-back .card-content');
    
    frontContent.textContent = currentSet[index].front;
    backContent.textContent = currentSet[index].back;
    
    // Update counter
    document.getElementById('current-card').textContent = index + 1;
    document.getElementById('total-cards').textContent = currentSet.length;
    
    // Reset flip state
    document.querySelector('.flashcard').classList.remove('flipped');
    
    // Update button states
    document.getElementById('prev-btn').disabled = index === 0;
    document.getElementById('next-btn').disabled = index === currentSet.length - 1;
    
    // Show/hide repeat section
    document.getElementById('repeat-section').style.display = 
        index === currentSet.length - 1 ? 'block' : 'none';
}

// Event Listeners
document.getElementById('prev-btn').addEventListener('click', function() {
    if (currentCard > 0) {
        currentCard--;
        showCard(currentCard);
    }
});

document.getElementById('next-btn').addEventListener('click', function() {
    if (currentCard < currentSet.length - 1) {
        currentCard++;
        showCard(currentCard);
    }
});

document.getElementById('flip-btn').addEventListener('click', function() {
    document.querySelector('.flashcard').classList.toggle('flipped');
});

document.getElementById('repeat-btn').addEventListener('click', function() {
    currentSet = getRandomCards(flashcards);
    currentCard = 0;
    document.getElementById('repeat-section').style.display = 'none';
    showCard(0);
});

// Add shuffle button event listener
document.getElementById('shuffle-btn').addEventListener('click', function() {
    currentSet = getRandomCards(flashcards);
    currentCard = 0;
    showCard(0);
    // Reset flip state
    document.querySelector('.flashcard').classList.remove('flipped');
});

// Initialize first card
showCard(0); 