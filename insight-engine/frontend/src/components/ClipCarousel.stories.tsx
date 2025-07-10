import type { Meta, StoryObj } from '@storybook/react';
import { SWRConfig } from 'swr';
import ClipCarousel, { ClipMetadata } from './ClipCarousel';

// --- 1. Storybook Metadata ---
const meta: Meta<typeof ClipCarousel> = {
  title: 'Components/ClipCarousel',
  component: ClipCarousel,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    initialClips: {
      control: 'object',
      description: 'An array of clip metadata objects to display.',
    },
  },
};

export default meta;
type Story = StoryObj<typeof ClipCarousel>;

// --- 2. Mock Data ---
const processingClips: ClipMetadata[] = [
  { clipId: '1', status: 'processing', title: 'Clip of a Red Car' },
  { clipId: '2', status: 'processing', title: 'Logo Detection' },
];

const availableClips: ClipMetadata[] = [
  {
    clipId: '3',
    status: 'available',
    url: 'https://www.w3schools.com/html/mov_bbb.mp4', // Placeholder video
    title: 'Opening Scene',
  },
  {
    clipId: '4',
    status: 'available',
    url: 'https://www.w3schools.com/html/mov_bbb.mp4',
    title: 'Product Shot',
  },
];

const mixedClips: ClipMetadata[] = [...availableClips, ...processingClips];

const errorClip: ClipMetadata = {
  clipId: '5',
  status: 'processing', // It starts as processing, but our mock will make it fail
  title: 'A Clip That Fails',
};

// --- 3. Story Definitions ---

// Story: Loading State
// Mocks the SWR fetcher to show clips in a 'processing' state.
export const Loading: Story = {
  args: {
    initialClips: mixedClips,
  },
  decorators: [
    (Story) => (
      <SWRConfig value={{ provider: () => new Map() }}>
        <div style={{ width: '600px', padding: '20px' }}>
          <Story />
        </div>
      </SWRConfig>
    ),
  ],
};

// Story: Complete State
// All clips are 'available' and do not trigger SWR polling.
export const Complete: Story = {
  args: {
    initialClips: availableClips,
  },
  decorators: [(Story) => <div style={{ width: '600px' }}><Story /></div>],
};

// Story: Error State
// Mocks an SWR fetcher that returns an error for a specific clip.
export const WithError: Story = {
  args: {
    initialClips: [availableClips[0], errorClip],
  },
  decorators: [
    (Story) => (
      <SWRConfig
        value={{
          fetcher: (url: string) => {
            if (url.includes(errorClip.clipId)) {
              return Promise.reject(new Error('Processing failed!'));
            }
            // For other clips, we can return a success state.
            return Promise.resolve({
              clipId: url.split('/').pop(),
              status: 'available',
              url: 'https://www.w3schools.com/html/mov_bbb.mp4',
            });
          },
        }}
      >
        <div style={{ width: '600px', padding: '20px' }}>
          <Story />
        </div>
      </SWRConfig>
    ),
  ],
};

// Story: Empty State
// No clips are provided to the component.
export const Empty: Story = {
  args: {
    initialClips: [],
  },
  decorators: [(Story) => <div style={{ width: '600px' }}><Story /></div>],
};