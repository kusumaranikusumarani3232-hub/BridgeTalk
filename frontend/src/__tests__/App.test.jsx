import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { Header } from '../components/Header';
import { ConnectionStatus } from '../components/ConnectionStatus';
import { SpeakerSelector } from '../components/SpeakerSelector';
import { ConversationList } from '../components/ConversationList';
import { InsightsPanel } from '../components/InsightsPanel';

describe('BridgeTalk Frontend Component Unit Tests', () => {
  it('renders Header title and tagline correctly', () => {
    render(<Header />);
    expect(screen.getByText('BridgeTalk')).toBeDefined();
    expect(screen.getByText('Real-time conversations without language barriers')).toBeDefined();
  });

  it('renders ConnectionStatus indicators', () => {
    render(
      <ConnectionStatus
        isConnected={true}
        assemblyaiReady={true}
        statusMessage="Ready"
        isRecording={false}
      />
    );
    expect(screen.getByText('Connected')).toBeDefined();
    expect(screen.getAllByText('Ready').length).toBeGreaterThan(0);
  });

  it('renders SpeakerSelector dual speakers', () => {
    render(
      <SpeakerSelector
        activeSpeaker="person_a"
        onSelectSpeaker={() => {}}
        isRecording={false}
      />
    );
    expect(screen.getByText('Person A')).toBeDefined();
    expect(screen.getByText('Person B')).toBeDefined();
    expect(screen.getByText('Hindi (हिन्दी)')).toBeDefined();
    expect(screen.getByText('English')).toBeDefined();
  });

  it('renders ConversationList with sample messages', () => {
    const sampleMsgs = [
      {
        id: '1',
        speaker: 'person_a',
        speaker_name: 'Person A',
        source_language: 'Hindi',
        target_language: 'English',
        original_text: 'Namaste kal meeting hai',
        translation: 'Hello tomorrow is meeting',
        translation_status: 'translated',
        timestamp: '10:00:00',
      },
    ];
    render(<ConversationList messages={sampleMsgs} onSpeakText={() => {}} />);
    expect(screen.getByText('"Namaste kal meeting hai"')).toBeDefined();
    expect(screen.getByText('"Hello tomorrow is meeting"')).toBeDefined();
  });

  it('renders InsightsPanel with items', () => {
    const sampleInsights = [
      { category: 'date', label: 'Date', value: 'Tomorrow', icon: '📅' },
    ];
    render(<InsightsPanel insights={sampleInsights} />);
    expect(screen.getByText('Tomorrow')).toBeDefined();
    expect(screen.getByText('Date')).toBeDefined();
  });

  it('triggers speech synthesis with full translated text on manual listen button click', () => {
    let spokenText = null;
    let spokenLang = null;
    const mockSpeak = (text, lang) => {
      spokenText = text;
      spokenLang = lang;
    };

    const sampleMsgs = [
      {
        id: '1',
        speaker: 'person_a',
        speaker_name: 'Person A',
        source_language: 'Hindi',
        target_language: 'English',
        original_text: 'Namaste, kya aap kal aa sakte hain?',
        translation: 'Hello, can you come tomorrow?',
        translation_status: 'translated',
        timestamp: '10:00:00',
      },
    ];

    render(<ConversationList messages={sampleMsgs} onSpeakText={mockSpeak} />);
    const listenBtn = screen.getByText('🔊 Listen');
    listenBtn.click();

    expect(spokenText).toBe('Hello, can you come tomorrow?');
    expect(spokenLang).toBe('en');
  });
});

