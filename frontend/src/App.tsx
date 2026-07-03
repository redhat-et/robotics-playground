import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import {
  Masthead,
  MastheadBrand,
  MastheadMain,
  Page,
  Content,
} from '@patternfly/react-core';
import RoboticsPlayground from './RoboticsPlayground';

const AppMasthead: React.FC = () => (
  <Masthead>
    <MastheadMain>
      <MastheadBrand>
        <Content component="h1" style={{ color: 'var(--pf-t--global--color--inverse--100)', margin: 0, fontSize: 'var(--pf-t--global--font--size--lg)' }}>
          Robotics Playground
        </Content>
      </MastheadBrand>
    </MastheadMain>
  </Masthead>
);

const App: React.FC = () => (
  <BrowserRouter>
    <Page masthead={<AppMasthead />}>
      <Routes>
        <Route path="/*" element={<RoboticsPlayground />} />
      </Routes>
    </Page>
  </BrowserRouter>
);

export default App;
