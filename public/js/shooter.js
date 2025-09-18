import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

// Game state and logic
const ShooterGame = () => {
  const [playerX, setPlayerX] = useState(400);
  const [targets, setTargets] = useState([]);
  const [bullets, setBullets] = useState([]);
  const gameAreaRef = useRef(null);

  // Target positions (randomly generated)
  useEffect(() => {
    const interval = setInterval(() => {
      if (!gameOver) {
        setTargets(prev => [
          ...prev,
          { id: Date.now(), x: Math.random() * 800, y: -20 }
        ]);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [gameOver]);

  // Handle bullet firing
  const shoot = (e) => {
    e.preventDefault();
    setBullets(prev => [
      ...prev,
      { id: Date.now(), x: playerX - 25, y: 600 }
    ]);
  };

  // Update bullets and check collisions
  useEffect(() => {
    if (!gameOver) {
      const interval = setInterval(() => {
        setBullets(prev => prev.map(bullet => ({
          ...bullet,
          y: bullet.y - 10
        })).filter(bullet => bullet.y > 0));

        // Collision detection (simplified)
        let gameWon = false;
        targets.forEach(target => {
          bullets.forEach(bullet => {
            if (
              target.x < bullet.x + 50 &&
              target.x + 40 > bullet.x &&
              target.y < bullet.y + 30 &&
              target.y + 30 > bullet.y
            ) {
              gameWon = true;
            }
          });
        });

        if (gameWon) gameOverRef.current = true;
      }, 50);
      return () => clearInterval(interval);
    }
  }, []);

  // Game over state
  const [gameOver, setGameOver] = useState(false);
  const gameOverRef = useRef(gameOver);

  useEffect(() => {
    gameOverRef.current = gameOver;
  }, [gameOver]);

  // Reset game
  const resetGame = () => {
    setTargets([]);
    setBullets([]);
    setGameOver(false);
  };

  return (
    <div>
      <h2>Shooter Game</h2>
      {!gameOver && (
        <>
          <button onClick={shoot}>Shoot!</button>
          <canvas ref={gameAreaRef} width="800" height="600"></canvas>
        </>
      )}
      {gameOver && <p>You Win! 🎉</p>}
      <button onClick={resetGame}>Restart</button>
    </div>
  );
};

// Render the game
ReactDOM.render(
  React.createElement(ShooterGame),
  document.getElementById('shooter-container')
);
