// Filled glyphs for both sides; CSS colours them white or black.
const glyphs = {K:'♚\uFE0E', Q:'♛\uFE0E', R:'♜\uFE0E', B:'♝\uFE0E', N:'♞\uFE0E', P:'♟\uFE0E'};
const names = {K:'king', Q:'queen', R:'rook', B:'bishop', N:'knight', P:'pawn'};
let state, selected = null, targets = [], busy = false;
const message = document.querySelector('#message');

async function request(action) {
  const response = await fetch('/api/action', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(action)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  if (action.action === 'move' || action.action === 'computer-move') placeSound(result.moves.at(-1).includes('x'));
  return result;
}

// A felted piece landing on a solid board, synthesized: decaying resonances (frequency Hz,
// level, decay s) plus a short contact tick. A capture is one deeper, louder, longer strike.
const RESONANCES = [[90, 0.5, 0.13], [180, 0.6, 0.1], [390, 0.45, 0.07], [850, 0.2, 0.046], [1425, 0.08, 0.03]];
let audio, master;
function placeSound(capture) {
  try {
    if (!audio) {
      audio = new AudioContext();
      master = audio.createDynamicsCompressor();
      master.threshold.value = -10; master.ratio.value = 4;
      master.connect(audio.destination);
    }
    const now = audio.currentTime + 0.01, out = audio.createGain();
    const pitch = (capture ? 0.78 : 1) * (1 + (Math.random() - 0.5) * 0.06);
    const length = capture ? 1.4 : 1;
    out.gain.value = capture ? 1.45 : 1;
    out.connect(master);
    for (const [frequency, level, decay] of RESONANCES) {
      const tone = audio.createOscillator(), envelope = audio.createGain();
      tone.frequency.value = frequency * pitch;
      envelope.gain.setValueAtTime(0, now);
      envelope.gain.linearRampToValueAtTime(level, now + 0.0015);
      envelope.gain.exponentialRampToValueAtTime(0.0001, now + decay * length);
      tone.connect(envelope).connect(out); tone.start(now); tone.stop(now + decay * length + 0.02);
    }
    const noise = audio.createBuffer(1, Math.ceil(audio.sampleRate * 0.007), audio.sampleRate);
    const samples = noise.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = (Math.random() * 2 - 1) * (1 - i / samples.length) ** 3;
    const tick = audio.createBufferSource(), band = audio.createBiquadFilter(), level = audio.createGain();
    tick.buffer = noise; band.type = 'bandpass'; band.frequency.value = 1000 * pitch; band.Q.value = 0.9;
    level.gain.value = 0.2;
    tick.connect(band).connect(level).connect(out); tick.start(now);
  } catch { /* Sound is decoration; a browser without audio still plays the game. */ }
}

function render() {
  const board = document.querySelector('#board');
  board.replaceChildren();
  for (let rank = 8; rank >= 1; rank--) {
    for (let file = 0; file < 8; file++) {
      const square = 'abcdefgh'[file] + rank, piece = state.board[square];
      const button = document.createElement('button');
      button.className = 'square ' + ((file + rank) % 2 ? 'dark' : 'light');
      button.classList.toggle('selected', selected === square);
      button.classList.toggle('target', targets.includes(square));
      button.classList.toggle('occupied', Boolean(piece));
      button.classList.toggle('checked', piece === state.turn + 'K'
        && (state.status === 'check' || state.status === 'checkmate'));
      button.dataset.square = square;
      button.setAttribute('aria-label', square + (piece ? ` ${piece[0] === 'w' ? 'White' : 'Black'} ${names[piece[1]]}` : ' empty'));
      button.setAttribute('aria-pressed', String(selected === square));
      if (piece) button.append(pieceGlyph(piece));
      if (file === 0) button.append(coordinate('rank', rank));
      if (rank === 1) button.append(coordinate('file', square[0]));
      button.onclick = () => clickSquare(square);
      board.append(button);
    }
  }
  const computer = state.opponent === 'computer';
  const side = computer ? (state.turn === 'w' ? 'Your move' : 'The computer is thinking')
                        : `${state.turn === 'w' ? 'White' : 'Black'} to move`;
  const winner = computer ? (state.winner === 'White' ? 'You win' : 'The computer wins')
                          : `${state.winner} wins`;
  document.querySelector('#turn').textContent =
    state.status === 'checkmate' ? `Checkmate. ${winner}`
    : state.status === 'stalemate' ? 'Stalemate. Draw'
    : state.status === 'check' ? `${side}. Check` : side;
  const pairs = [];
  for (let i = 0; i < state.moves.length; i += 2) pairs.push(state.moves.slice(i, i + 2));
  document.querySelector('#moves').replaceChildren(...pairs.map(pair => {
    const item = document.createElement('li');
    for (const move of pair) {
      const cell = document.createElement('span'); cell.textContent = move; item.append(cell);
    }
    return item;
  }));
  document.querySelector('#captured-panel').hidden = !Object.hasOwn(state, 'captured');
  const captured = state.captured || [];
  document.querySelector('#captured').replaceChildren(...captured.map(pieceGlyph));
  if (!captured.length) document.querySelector('#captured').textContent = 'None';
}

function pieceGlyph(piece) {
  const glyph = document.createElement('span');
  glyph.className = 'piece ' + (piece[0] === 'w' ? 'white' : 'black');
  glyph.textContent = glyphs[piece[1]];
  return glyph;
}

function coordinate(kind, text) {
  const label = document.createElement('small');
  label.className = kind; label.textContent = text;
  return label;
}

// Against the computer, it answers after a short pause so each move is seen and heard.
async function computerReply() {
  const over = state.status === 'checkmate' || state.status === 'stalemate';
  if (state.opponent !== 'computer' || state.turn !== 'b' || over) return;
  await new Promise(resolve => setTimeout(resolve, 500));
  state = await request({action: 'computer-move'});
  render();
}

async function clickSquare(square) {
  if (busy) return;
  busy = true;
  message.textContent = '';
  try {
    if (selected && targets.includes(square)) {
      state = await request({action:'move', source:selected, target:square});
      selected = null; targets = [];
    } else if (selected === square) {
      selected = null; targets = [];
    } else {
      targets = (await request({action:'legal', source:square})).targets;
      selected = state.board[square]?.[0] === state.turn ? square : null;
    }
    render();
    await computerReply();
  } catch (error) { message.textContent = error.message; }
  finally { busy = false; }
}

document.querySelector('#controls').onclick = async event => {
  const button = event.target.closest('button');
  if (!button?.dataset.action || busy) return;
  busy = true;
  try {
    const action = button.dataset.action;
    state = await request({action, opponent: button.dataset.opponent});
    selected = null; targets = [];
    message.textContent = {save: 'Game saved', load: 'Game loaded'}[action] ?? '';
    render();
    // A game saved while the computer was to move continues with its reply.
    if (action === 'load') await computerReply();
  } catch (error) { message.textContent = error.message; }
  finally { busy = false; }
};

try {
  const response = await fetch('/api/state');
  if (!response.ok) throw new Error('Could not load the game');
  state = await response.json(); render();
} catch (error) { message.textContent = error.message; }
